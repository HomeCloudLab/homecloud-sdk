"""Auth model: Access Keys primary; console JWT/MFA interactive-only."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from homecloud_core.errors import NotConfiguredError, NotLoggedInError
from homecloud_sdk import HomeCloud, HomeCloudClient


def test_explicit_access_keys_without_credentials_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("HOMECLOUD_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("HC_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("HOMECLOUD_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.delenv("HC_SECRET_ACCESS_KEY", raising=False)

    captured: dict[str, str] = {}

    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def close(self) -> None:
            return None

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            captured["path"] = request.url.path
            captured["access_key"] = request.headers.get("X-Homecloud-Access-Key-Id", "")
            if request.url.path == "/access-key/whoami":
                return httpx.Response(200, json={"account_id": "acc-explicit"}, request=request)
            return httpx.Response(200, json={"message_id": "m1"}, request=request)

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)

    client = HomeCloud(
        access_key="HCAKINLINE",
        secret_key="secret-inline",
        apex="example.test",
    )
    assert client._ctx.transport._mfa_resolver is None
    result = client.mq.send("q", {"a": 1})
    assert result["message_id"] == "m1"
    assert captured["access_key"] == "HCAKINLINE"
    client.close()


def test_from_credentials_and_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("HC_ACCESS_KEY_ID", "HCAKENV")
    monkeypatch.setenv("HC_SECRET_ACCESS_KEY", "secret-env")
    monkeypatch.setenv("HC_APEX", "env.example")

    via_env = HomeCloudClient.from_env()
    assert via_env._ctx.profile.access_key_id == "HCAKENV"
    assert via_env._ctx.profile.apex == "env.example"
    assert via_env._ctx._interactive_mfa is False
    via_env.close()

    via_cred = HomeCloudClient.from_credentials("HCAK1", "sec", apex="x.test")
    assert via_cred._ctx.profile.access_key_id == "HCAK1"
    assert via_cred._ctx.transport._mfa_resolver is None
    via_cred.close()


def test_default_sdk_client_disables_interactive_mfa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    client = HomeCloudClient()
    assert client._ctx._interactive_mfa is False
    assert client._ctx.transport._mfa_resolver is None
    client.close()


def test_console_ops_require_jwt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    client = HomeCloudClient.from_credentials("HCAK1", "sec", apex="example.test")
    with pytest.raises(NotLoggedInError):
        client.so.list_buckets()
    with pytest.raises(NotLoggedInError):
        client.queues.list()
    with pytest.raises(NotLoggedInError):
        client.apps.list()
    client.close()


def test_data_plane_requires_access_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    client = HomeCloudClient()
    with pytest.raises(NotConfiguredError):
        client.mq.send("q", {"x": 1})
    client.close()
