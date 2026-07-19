from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from homecloud_core.config import ProfileConfig, upsert_profile
from homecloud_core.context import CoreContext
from homecloud_core.env import env_first, env_profile


def test_env_first_prefers_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMECLOUD_PROFILE", "prod")
    monkeypatch.setenv("HC_PROFILE", "dev")
    assert env_first("HOMECLOUD_PROFILE", "HC_PROFILE") == "prod"
    assert env_profile() == "prod"


def test_hc_profile_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HOMECLOUD_PROFILE", raising=False)
    monkeypatch.setenv("HC_PROFILE", "staging")
    assert env_profile() == "staging"


def test_context_uses_hc_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("HC_PROFILE", "prod")
    monkeypatch.delenv("HOMECLOUD_PROFILE", raising=False)

    upsert_profile(
        ProfileConfig(
            name="prod",
            apex="example.test",
            default_account_id="acc-prod",
            access_key_id="HCAKPROD",
            secret_access_key="secret-prod",
        ),
        make_default=False,
    )
    upsert_profile(
        ProfileConfig(
            name="default",
            apex="example.test",
            default_account_id="acc-default",
            access_key_id="HCAKDEF",
            secret_access_key="secret-def",
        ),
        make_default=True,
    )

    ctx = CoreContext()
    assert ctx.profile_name == "prod"
    assert ctx.profile.access_key_id == "HCAKPROD"


def test_context_honors_credentials_default_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("HOMECLOUD_PROFILE", raising=False)
    monkeypatch.delenv("HC_PROFILE", raising=False)

    cred_file = tmp_path / "credentials"
    cred_file.write_text(
        json.dumps(
            {
                "version": 2,
                "default_profile": "prod",
                "profiles": {
                    "prod": {
                        "apex": "example.test",
                        "default_account_id": "acc-prod",
                        "access_key_id": "HCAKPROD",
                        "secret_access_key": "secret",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    ctx = CoreContext()
    assert ctx.profile_name == "prod"
    assert ctx.profile.access_key_id == "HCAKPROD"


def test_apex_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("HC_APEX", "custom.example")
    monkeypatch.delenv("HOMECLOUD_APEX", raising=False)

    upsert_profile(
        ProfileConfig(
            name="default",
            apex="example.test",
            default_account_id="acc-1",
            access_key_id="HCAK1",
            secret_access_key="secret",
        )
    )

    ctx = CoreContext()
    assert ctx.profile.apex == "custom.example"


def test_login_sends_username(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    captured: dict[str, object] = {}

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url)
            if "auth/login" in url:
                captured["json"] = kwargs.get("json")
                return httpx.Response(
                    200, json={"access_token": "tok-1"}, request=request
                )
            return httpx.Response(200, json={"items": []}, request=request)

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)

    CoreContext().login("alice", "secret123")
    assert captured["json"] == {"username": "alice", "password": "secret123"}


def test_whoami_resolves_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    upsert_profile(
        ProfileConfig(
            name="default",
            apex="example.test",
            access_key_id="HCAK1",
            secret_access_key="secret",
        )
    )

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            assert request.url.path == "/access-key/whoami"
            return httpx.Response(200, json={"account_id": "acc-from-whoami"}, request=request)

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)

    assert CoreContext().account_id() == "acc-from-whoami"
