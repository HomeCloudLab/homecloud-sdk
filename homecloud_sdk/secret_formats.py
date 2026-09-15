"""Flat secret map codecs: json | env | yaml.

Canonical model: dict[str, str]. Nested structures, non-string JSON values,
and duplicate keys are rejected (no last-wins).
"""

from __future__ import annotations

import json
import re
from typing import Iterable, Literal

SecretFormat = Literal["json", "env", "yaml"]


class SecretFormatError(ValueError):
    """Invalid secret format document."""


def parse_secret_format(fmt: SecretFormat, text: str) -> dict[str, str]:
    if fmt == "json":
        return parse_secret_json(text)
    if fmt == "env":
        return parse_secret_env(text)
    if fmt == "yaml":
        return parse_secret_yaml(text)
    raise SecretFormatError(f"Unsupported format: {fmt}")


def serialize_secret_format(
    fmt: SecretFormat,
    values: dict[str, str],
    *,
    key_order: Iterable[str] | None = None,
) -> str:
    if fmt == "json":
        return serialize_secret_json(values, key_order=key_order)
    if fmt == "env":
        return serialize_secret_env(values, key_order=key_order)
    if fmt == "yaml":
        return serialize_secret_yaml(values, key_order=key_order)
    raise SecretFormatError(f"Unsupported format: {fmt}")


def parse_secret_json(text: str) -> dict[str, str]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SecretFormatError("Invalid JSON") from exc
    return _assert_flat_string_map(parsed, "JSON")


def serialize_secret_json(
    values: dict[str, str],
    *,
    key_order: Iterable[str] | None = None,
) -> str:
    ordered = _order_dict(values, key_order)
    return json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"


def parse_secret_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for i, line in enumerate(text.splitlines(), start=1):
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        eq = trimmed.find("=")
        if eq <= 0:
            raise SecretFormatError(f"ENV line {i}: expected KEY=VALUE")
        key = trimmed[:eq].strip()
        if not key or re.search(r"\s", key):
            raise SecretFormatError(f"ENV line {i}: invalid key")
        if key in out:
            raise SecretFormatError(f'ENV: duplicate key "{key}"')
        out[key] = _unquote_env_value(trimmed[eq + 1 :])
    return out


def serialize_secret_env(
    values: dict[str, str],
    *,
    key_order: Iterable[str] | None = None,
) -> str:
    lines = [f"{key}={_quote_env_value(value)}" for key, value in _order_items(values, key_order)]
    return ("\n".join(lines) + "\n") if lines else ""


def parse_secret_yaml(text: str) -> dict[str, str]:
    """Minimal flat YAML mapping parser (no PyYAML dependency)."""
    out: dict[str, str] = {}
    saw_document = False
    for i, raw_line in enumerate(text.splitlines(), start=1):
        if re.match(r"^\s+#", raw_line) or raw_line.strip() == "":
            continue
        if re.match(r"^\s+\S", raw_line):
            raise SecretFormatError(f"YAML line {i}: nested/indented entries are not allowed")
        line = raw_line.strip()
        if line in {"---", "..."}:
            if saw_document and line == "---":
                raise SecretFormatError("YAML: multiple documents are not allowed")
            continue
        if line.startswith("- "):
            raise SecretFormatError(f"YAML line {i}: lists are not allowed")
        match = re.match(r"^([^:#\s][^:#]*?)\s*:\s*(.*)$", line)
        if not match:
            raise SecretFormatError(f'YAML line {i}: expected "key: value"')
        key = match.group(1).strip()
        value_part = match.group(2).strip()
        if not key:
            raise SecretFormatError(f"YAML line {i}: empty key")
        if key in out:
            raise SecretFormatError(f'YAML: duplicate key "{key}"')
        if value_part in {"", "|", ">", "|-"}:
            raise SecretFormatError(f"YAML line {i}: multiline / nested values are not allowed")
        if value_part.startswith("{") or value_part.startswith("["):
            raise SecretFormatError(f"YAML line {i}: nested structures are not allowed")
        if not (
            (value_part.startswith('"') and value_part.endswith('"'))
            or (value_part.startswith("'") and value_part.endswith("'"))
        ):
            hash_idx = value_part.find(" #")
            if hash_idx >= 0:
                value_part = value_part[:hash_idx].strip()
        out[key] = _unquote_yaml_scalar(value_part)
        saw_document = True
    return out


def serialize_secret_yaml(
    values: dict[str, str],
    *,
    key_order: Iterable[str] | None = None,
) -> str:
    lines = [f"{key}: {_quote_yaml_scalar(value)}" for key, value in _order_items(values, key_order)]
    return ("\n".join(lines) + "\n") if lines else ""


def _assert_flat_string_map(value: object, context: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise SecretFormatError(f"{context}: expected a flat object of string keys and values")
    out: dict[str, str] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not key:
            raise SecretFormatError(f"{context}: empty key is not allowed")
        if not isinstance(raw, str):
            raise SecretFormatError(
                f'{context}: key "{key}" must be a string value '
                "(nested or non-string values are rejected)"
            )
        if key in out:
            raise SecretFormatError(f'{context}: duplicate key "{key}"')
        out[key] = raw
    return out


def _order_items(
    values: dict[str, str],
    key_order: Iterable[str] | None,
) -> list[tuple[str, str]]:
    if key_order is None:
        return [(key, values[key]) for key in sorted(values)]
    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []
    for key in key_order:
        if key in values and key not in seen:
            ordered.append((key, values[key]))
            seen.add(key)
    for key in sorted(values):
        if key not in seen:
            ordered.append((key, values[key]))
    return ordered


def _order_dict(
    values: dict[str, str],
    key_order: Iterable[str] | None,
) -> dict[str, str]:
    return dict(_order_items(values, key_order))


def _unquote_env_value(raw: str) -> str:
    value = raw.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        inner = value[1:-1]
        if value.startswith('"'):
            return (
                inner.replace(r"\\", "\0")
                .replace(r"\n", "\n")
                .replace(r"\r", "\r")
                .replace(r"\t", "\t")
                .replace(r"\"", '"')
                .replace("\0", "\\")
            )
        return inner
    return raw.lstrip()


def _quote_env_value(value: str) -> str:
    if value == "" or re.search(r'[\s#"\']', value):
        escaped = (
            value.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'
    return value


def _unquote_yaml_scalar(raw: str) -> str:
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        quote = raw[0]
        inner = raw[1:-1]
        if quote == '"':
            return inner.replace(r"\\", "\0").replace(r"\n", "\n").replace(r"\"", '"').replace("\0", "\\")
        return inner.replace("''", "'")
    if raw == "~" or raw.lower() == "null":
        raise SecretFormatError("YAML: null values are not allowed")
    return raw


def _quote_yaml_scalar(value: str) -> str:
    if (
        value == ""
        or re.search(r"[:#\n\r\t{}[\],&*!|>%@`]", value)
        or re.search(r"^\s|\s$", value)
        or re.match(r"^(true|false|null|~)$", value, re.I)
    ):
        return json.dumps(value)
    return value
