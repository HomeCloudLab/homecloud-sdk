"""Tests for flat secret map codecs."""

from __future__ import annotations

import pytest

from homecloud_sdk.secret_formats import (
    SecretFormatError,
    parse_secret_env,
    parse_secret_format,
    parse_secret_json,
    parse_secret_yaml,
    serialize_secret_env,
    serialize_secret_format,
    serialize_secret_json,
)


SAMPLE = {"API_KEY": "abc", "DATABASE_URL": "postgres://x"}


def test_env_accepts_no_trailing_newline() -> None:
    assert parse_secret_env("API_KEY=x") == {"API_KEY": "x"}
    assert serialize_secret_env({"API_KEY": "x"}) == "API_KEY=x"
    assert not serialize_secret_env({"API_KEY": "x"}).endswith("\n")


@pytest.mark.parametrize("fmt", ["json", "env", "yaml"])
def test_round_trip(fmt: str) -> None:
    text = serialize_secret_format(fmt, SAMPLE)  # type: ignore[arg-type]
    assert parse_secret_format(fmt, text) == SAMPLE  # type: ignore[arg-type]


def test_reject_nested_json() -> None:
    with pytest.raises(SecretFormatError):
        parse_secret_json('{"a":{"b":"c"}}')


def test_reject_non_string_json() -> None:
    with pytest.raises(SecretFormatError):
        parse_secret_json('{"a":1}')


def test_reject_duplicate_env() -> None:
    with pytest.raises(SecretFormatError, match="duplicate"):
        parse_secret_env("A=1\nA=2\n")


def test_reject_nested_yaml() -> None:
    with pytest.raises(SecretFormatError):
        parse_secret_yaml("a:\n  b: c\n")


def test_reject_duplicate_yaml() -> None:
    with pytest.raises(SecretFormatError, match="duplicate"):
        parse_secret_yaml("a: 1\na: 2\n")


def test_env_comments_and_quotes() -> None:
    assert parse_secret_env('# hi\nTOKEN="a b"\n') == {"TOKEN": "a b"}


def test_json_key_order() -> None:
    text = serialize_secret_json({"b": "2", "a": "1"}, key_order=["b", "a"])
    assert text.index('"b"') < text.index('"a"')


def test_env_quotes_spaces() -> None:
    assert '"hello world"' in serialize_secret_env({"X": "hello world"})
