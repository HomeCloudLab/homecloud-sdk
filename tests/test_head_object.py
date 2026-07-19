from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from homecloud_sdk import HomeCloud


def test_head_object_returns_clean_metadata_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    captured: dict[str, str] = {}

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def close(self) -> None:
            return None

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            captured["path"] = request.url.path
            if request.url.path == "/access-key/whoami":
                return httpx.Response(200, json={"account_id": "acc-1"}, request=request)
            assert "/metadata" in request.url.path
            assert method == "GET"
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
                    "extra_noise": "drop-me",
                    "body": "SHOULD_NOT_LEAK",
                },
                request=request,
            )

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)

    client = HomeCloud(access_key="HCAK1", secret_key="sec", apex="example.test")
    meta = client.so.head_object("bucket", "docs/a.txt")
    client.close()

    assert captured["path"].endswith("/metadata")
    assert meta == {
        "key": "docs/a.txt",
        "size": 12,
        "etag": "abc",
        "content_type": "text/plain",
        "last_modified": "2026-01-01T00:00:00Z",
        "metadata": {"x-amz-meta-owner": "sa"},
        "tags": {"env": "test"},
    }
    client.close()

    # Alias still works
    client2 = HomeCloud(access_key="HCAK1", secret_key="sec", apex="example.test")
    assert client2.so.object_metadata("bucket", "docs/a.txt")["size"] == 12
    client2.close()
