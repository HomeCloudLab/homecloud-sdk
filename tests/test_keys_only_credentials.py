"""Credentials file stores Access Keys only — apex/account resolved at runtime."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from homecloud_core.config import ProfileConfig, load_credentials, upsert_profile
from homecloud_core.context import CoreContext
from homecloud_core.defaults import DEFAULT_APEX
from homecloud_core.session import load_session


def test_configure_persists_keys_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("HOMECLOUD_APEX", raising=False)
    monkeypatch.delenv("HC_APEX", raising=False)

    CoreContext.configure_profile(
        profile_name="default",
        access_key_id="HCAKONLY",
        secret_access_key="secret-only",
        default_account_id="should-not-persist",
        apex="should-not-persist.example",
    )

    raw = json.loads((tmp_path / "credentials").read_text(encoding="utf-8"))
    profile = raw["profiles"]["default"]
    assert set(profile.keys()) == {"access_key_id", "secret_access_key"}
    assert profile["access_key_id"] == "HCAKONLY"
    assert "apex" not in profile
    assert "default_account_id" not in profile

    loaded = load_credentials().get_profile()
    assert loaded.access_key_id == "HCAKONLY"
    assert loaded.default_account_id is None
    assert loaded.apex == DEFAULT_APEX


def test_import_console_export_keys_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))

    CoreContext.import_credentials_file(
        {
            "version": 2,
            "default_profile": "default",
            "profiles": {
                "default": {
                    "access_key_id": "HCAKUI",
                    "secret_access_key": "ui-secret",
                }
            },
        }
    )

    raw = json.loads((tmp_path / "credentials").read_text(encoding="utf-8"))
    assert raw["profiles"]["default"] == {
        "access_key_id": "HCAKUI",
        "secret_access_key": "ui-secret",
    }


def test_account_resolved_via_whoami_then_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("HOMECLOUD_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("HC_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("HOMECLOUD_APEX", raising=False)

    upsert_profile(
        ProfileConfig(
            name="default",
            access_key_id="HCAK1",
            secret_access_key="secret",
        )
    )

    calls: list[str] = []

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method: str, url: str, **kwargs):
            path = httpx.URL(url).path
            calls.append(path)
            if path.endswith("/access-key/whoami"):
                return httpx.Response(200, json={"account_id": "acc-from-whoami"})
            return httpx.Response(200, json={"ok": True, "path": path})

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)

    ctx = CoreContext()
    assert ctx.profile.apex == DEFAULT_APEX
    assert ctx.profile.default_account_id is None

    account = ctx.account_id()
    assert account == "acc-from-whoami"
    assert any(c.endswith("/access-key/whoami") for c in calls)

    session = load_session().get("default")
    assert session.active_account_id == "acc-from-whoami"

    # Second resolution uses session — no second whoami needed for account_id cache,
    # but even a fresh context should use session before whoami.
    calls.clear()
    ctx2 = CoreContext()
    assert ctx2.account_id() == "acc-from-whoami"
    assert not any(c.endswith("/access-key/whoami") for c in calls)


def test_mq_send_with_keys_only_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))

    (tmp_path / "credentials").write_text(
        json.dumps(
            {
                "version": 2,
                "default_profile": "default",
                "profiles": {
                    "default": {
                        "access_key_id": "HCAK1",
                        "secret_access_key": "secret",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, str] = {}

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(
                method, url, headers=kwargs.get("headers"), json=kwargs.get("json")
            )
            path = request.url.path
            if path.endswith("/access-key/whoami"):
                return httpx.Response(200, json={"account_id": "acc-1"})
            captured["method"] = request.method
            captured["path"] = path
            captured["access_key"] = request.headers.get("X-Homecloud-Access-Key-Id", "")
            return httpx.Response(200, json={"message_id": "msg-1"})

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)

    from homecloud_sdk import HomeCloudClient

    result = HomeCloudClient().mq.send("demo-queue", {"hello": "world"})
    assert result["message_id"] == "msg-1"
    assert captured["path"] == "/acc-1/demo-queue/messages"
    assert captured["access_key"] == "HCAK1"
