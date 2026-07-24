from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from homecloud_sdk import HomeCloudClient


def _write_creds(tmp_path: Path) -> None:
    cred_file = tmp_path / "credentials"
    cred_file.write_text(
        json.dumps(
            {
                "version": 2,
                "default_profile": "default",
                "profiles": {
                    "default": {
                        "apex": "example.test",
                        "default_account_id": "acc-1",
                        "access_key_id": "HCAK1",
                        "secret_access_key": "secret",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_sdk_mq_delete_and_purge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_creds(tmp_path)
    monkeypatch.setenv("HOMECLOUD_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))

    calls: list[dict[str, Any]] = []

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url)
            calls.append({"method": request.method, "path": request.url.path})
            return httpx.Response(204)

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)
    client = HomeCloudClient()
    client.mq.delete("demo-queue", 42)
    client.mq.purge("demo-queue")
    client.mq.purge_dlq("demo-queue")
    assert calls[0] == {"method": "DELETE", "path": "/acc-1/demo-queue/messages/42"}
    assert calls[1] == {"method": "POST", "path": "/acc-1/demo-queue/purge"}
    assert calls[2] == {"method": "POST", "path": "/acc-1/demo-queue/dlq/purge"}


def test_sdk_mq_receive_dlq(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _write_creds(tmp_path)
    monkeypatch.setenv("HOMECLOUD_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))

    captured: dict[str, Any] = {}

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url)
            captured["path"] = request.url.path
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "sequence": 1,
                            "body": "x",
                            "created_at": "2026-07-24T00:00:00Z",
                        }
                    ],
                    "total": 1,
                },
            )

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)
    items = HomeCloudClient().mq.receive_dlq("demo-queue", max_messages=2)
    assert captured["path"] == "/acc-1/demo-queue/dlq/messages"
    assert items[0]["created_at"] == "2026-07-24T00:00:00Z"
