"""Async head_object and preferred import path."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from homecloud import AsyncHomeCloud, HomeCloud
from homecloud_sdk import AsyncHomeCloud as AsyncFromSdk


def test_async_head_object_returns_clean_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    captured: dict[str, str] = {}

    class MockAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def aclose(self) -> None:
            pass

        async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
            request = httpx.Request(method, url, headers=kwargs.get("headers"))  # type: ignore[arg-type]
            captured["path"] = str(httpx.URL(url).path)
            assert "/metadata" in request.url.path
            return httpx.Response(
                200,
                json={
                    "key": "docs/a.txt",
                    "size": 12,
                    "etag": "abc",
                    "content_type": "text/plain",
                    "last_modified": "2026-01-01T00:00:00Z",
                    "metadata": {"x-amz-meta-owner": "sa"},
                    "tags": {"env": "test"},
                },
                request=request,
            )

    monkeypatch.setattr("homecloud_core.async_transport.httpx.AsyncClient", MockAsyncClient)

    async def run() -> dict:
        async with AsyncHomeCloud(
            access_key_id="HCAKTEST",
            secret_access_key="secret",
            account_id="acc-1",
            apex="example.test",
        ) as client:
            return await client.so.head_object("bucket", "docs/a.txt")

    meta = asyncio.run(run())
    assert captured["path"].endswith("/metadata")
    assert meta["size"] == 12
    assert meta["etag"] == "abc"
    assert meta["metadata"] == {"x-amz-meta-owner": "sa"}
    assert meta["tags"] == {"env": "test"}


def test_homecloud_package_reexports() -> None:
    assert HomeCloud is not None
    assert AsyncHomeCloud is AsyncFromSdk
