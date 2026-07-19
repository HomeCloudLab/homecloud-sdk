"""SO URI and presigned URL helpers."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from homecloud import AsyncHomeCloud, HomeCloud


def test_get_object_uri_and_presigned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    paths: list[str] = []

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def close(self) -> None:
            return None

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            path = request.url.path
            paths.append(path)
            if path.endswith("/uri"):
                return httpx.Response(
                    200,
                    json={
                        "so_uri": "so://bucket/docs/a.txt",
                        "https_url": "https://bucket.so.example.test/docs/a.txt",
                        "https_requires_public": True,
                    },
                    request=request,
                )
            if path.endswith("/presigned"):
                assert kwargs.get("params", {}).get("expires") == 120
                return httpx.Response(
                    200,
                    json={"url": "https://signed.example/x?X-Amz-Signature=1", "expires_in_seconds": 120},
                    request=request,
                )
            raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)

    client = HomeCloud(
        access_key="HCAK1",
        secret_key="sec",
        account_id="acc-1",
        apex="example.test",
    )
    uri = client.so.get_object_uri("bucket", "docs/a.txt")
    signed = client.so.generate_presigned_url("bucket", "docs/a.txt", expires=120)
    client.close()

    assert uri["so_uri"] == "so://bucket/docs/a.txt"
    assert uri["https_url"].startswith("https://")
    assert uri["https_requires_public"] is True
    assert signed["url"].startswith("https://")
    assert signed["expires_in_seconds"] == 120
    assert any(p.endswith("/uri") for p in paths)
    assert any(p.endswith("/presigned") for p in paths)


def test_async_get_object_uri_and_presigned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))

    class MockAsyncClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def aclose(self) -> None:
            pass

        async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
            request = httpx.Request(method, url, headers=kwargs.get("headers"))  # type: ignore[arg-type]
            path = request.url.path
            if path.endswith("/uri"):
                return httpx.Response(
                    200,
                    json={
                        "so_uri": "so://bucket/docs/a.txt",
                        "https_url": "https://bucket.so.example.test/docs/a.txt",
                        "https_requires_public": True,
                    },
                    request=request,
                )
            if path.endswith("/presigned"):
                return httpx.Response(
                    200,
                    json={"url": "https://signed.example/y", "expires_in_seconds": 3600},
                    request=request,
                )
            raise AssertionError(path)

    monkeypatch.setattr("homecloud_core.async_transport.httpx.AsyncClient", MockAsyncClient)

    async def run() -> tuple[dict, dict]:
        async with AsyncHomeCloud(
            access_key_id="HCAK1",
            secret_access_key="sec",
            account_id="acc-1",
            apex="example.test",
        ) as client:
            uri = await client.so.get_object_uri("bucket", "docs/a.txt")
            signed = await client.so.generate_presigned_url("bucket", "docs/a.txt")
            return uri, signed

    uri, signed = asyncio.run(run())
    assert uri["so_uri"].startswith("so://")
    assert signed["url"].startswith("https://")
