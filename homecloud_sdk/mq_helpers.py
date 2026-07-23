"""Shared MQ send helpers (single vs batch)."""

from __future__ import annotations

import json
from typing import Any

from homecloud_core.errors import HomeCloudError

MQ_BATCH_MAX = 10


def _entry_body_str(value: Any) -> str:
    if isinstance(value, str):
        if not value:
            raise HomeCloudError("mq.send batch entry body must be non-empty")
        return value
    return json.dumps(value)


def build_mq_batch_entries(items: list[Any]) -> list[dict[str, Any]]:
    """Normalize a list of bodies / entry dicts into API ``entries`` (1–10)."""
    if not items or len(items) > MQ_BATCH_MAX:
        raise HomeCloudError(f"mq.send batch requires 1–{MQ_BATCH_MAX} messages")

    entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(items):
        if isinstance(item, dict) and isinstance(item.get("body"), str):
            entry_id = str(item.get("id") if item.get("id") is not None else index)
            body = item["body"]
            if not body:
                raise HomeCloudError("mq.send batch entry body must be non-empty")
            headers = item.get("headers")
            entry: dict[str, Any] = {"id": entry_id, "body": body}
            if headers:
                entry["headers"] = headers
        else:
            entry_id = str(index)
            entry = {"id": entry_id, "body": _entry_body_str(item)}

        if entry_id in seen_ids:
            raise HomeCloudError("mq.send batch entry ids must be unique")
        seen_ids.add(entry_id)
        entries.append(entry)
    return entries
