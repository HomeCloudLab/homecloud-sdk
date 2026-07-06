from __future__ import annotations

import json
from pathlib import Path

import pytest

from homecloud_core.account import resolve_account_id
from homecloud_core.config import ProfileConfig
from homecloud_core.session import ProfileSession


def test_account_resolution_priority() -> None:
    profile = ProfileConfig(name="default", default_account_id="default-acc")
    session = ProfileSession(active_account_id="active-acc", last_used_account_id="last-acc")
    assert resolve_account_id(profile, session) == "active-acc"

    session_no_active = ProfileSession(last_used_account_id="last-acc")
    assert resolve_account_id(profile, session_no_active) == "default-acc"

    session_last = ProfileSession(last_used_account_id="last-acc")
    profile_no_default = ProfileConfig(name="default")
    assert resolve_account_id(profile_no_default, session_last) == "last-acc"


def test_sdk_client_mq_send(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import httpx

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
    monkeypatch.setenv("HOMECLOUD_CREDENTIALS_FILE", str(cred_file))
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))

    captured: dict[str, str] = {}

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url, headers=kwargs.get("headers"), json=kwargs.get("json"))
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["access_key"] = request.headers.get("X-Homecloud-Access-Key-Id", "")
            return httpx.Response(200, json={"message_id": "msg-1"})

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)

    from homecloud_sdk import HomeCloudClient

    result = HomeCloudClient().mq.send("demo-queue", {"hello": "world"})
    assert result["message_id"] == "msg-1"
    assert captured["method"] == "POST"
    assert captured["path"] == "/acc-1/demo-queue/messages"
    assert captured["access_key"] == "HCAK1"
