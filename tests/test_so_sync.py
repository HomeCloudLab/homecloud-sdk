"""Unified so.sync — mode routing and bucket↔bucket copy."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from homecloud_core.errors import HomeCloudError
from homecloud_sdk.services import SoAPI


def _so_api() -> SoAPI:
    ctx = MagicMock()
    ctx.require_access_key = MagicMock()
    return SoAPI(ctx)


def test_sync_rejects_two_local_paths() -> None:
    api = _so_api()
    with pytest.raises(HomeCloudError, match="so://"):
        api.sync("./a", "./b")


def test_sync_same_remote_rejected() -> None:
    api = _so_api()
    with pytest.raises(HomeCloudError, match="same"):
        api._sync_bucket_to_bucket("docs", "docs", source_prefix="a", destination_prefix="a")


def test_sync_bucket_to_bucket_copies_and_deletes(monkeypatch: pytest.MonkeyPatch) -> None:
    api = _so_api()
    source_items = [
        {"key": "src/a.txt", "size": 3, "is_dir": False},
        {"key": "src/sub/b.txt", "size": 5, "is_dir": False},
    ]
    dest_items = [
        {"key": "dst/a.txt", "size": 3, "is_dir": False},
        {"key": "dst/old.txt", "size": 1, "is_dir": False},
    ]

    def fake_remote(bucket: str, prefix: str) -> dict[str, dict[str, Any]]:
        items = source_items if bucket == "alpha" else dest_items
        return {item["key"]: item for item in items if item["key"].startswith(prefix) or not prefix}

    monkeypatch.setattr(api, "_remote_objects_for_sync", fake_remote)

    copied: list[tuple[str, str, str, str | None]] = []
    deleted: list[tuple[str, str]] = []

    def fake_copy(
        bucket_name: str,
        source_key: str,
        destination_key: str,
        *,
        source_bucket: str | None = None,
    ) -> dict[str, Any]:
        copied.append((bucket_name, source_key, destination_key, source_bucket))
        return {"key": destination_key}

    def fake_delete(bucket_name: str, object_key: str) -> None:
        deleted.append((bucket_name, object_key))

    monkeypatch.setattr(api, "copy", fake_copy)
    monkeypatch.setattr(api, "delete", fake_delete)

    result = api.sync("so://alpha/src/", "so://beta/dst/", delete=True, skip=True)
    assert result["skipped"] == 1  # a.txt same size
    assert result["copied"] == 1  # sub/b.txt
    assert result["deleted"] == 1  # old.txt
    assert copied == [("beta", "src/sub/b.txt", "dst/sub/b.txt", "alpha")]
    assert deleted == [("beta", "dst/old.txt")]


def test_sync_dispatches_local_to_bucket(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    api = _so_api()
    called: dict[str, Any] = {}

    def fake_upload(local_dir, bucket_name, **kwargs):
        called["args"] = (str(local_dir), bucket_name, kwargs.get("prefix"))
        return {"uploaded": 0, "skipped": 0, "deleted": 0}

    monkeypatch.setattr(api, "_sync_local_to_bucket", fake_upload)
    local = tmp_path / "dist"
    local.mkdir()
    api.sync(local, "so://site/www/")
    assert called["args"] == (str(local), "site", "www")
