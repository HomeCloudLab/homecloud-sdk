"""HomeCloud.from_sts / from_function_context."""

from __future__ import annotations

import os

from homecloud_sdk import HomeCloud


def test_from_sts_so_sets_session_and_base(monkeypatch) -> None:
    monkeypatch.delenv("HC_ACCOUNT_ID", raising=False)
    client = HomeCloud.from_sts(
        {
            "resource_type": "so",
            "resource_name": "my-bucket",
            "access_key_id": "HCSAKTEST",
            "secret_access_key": "secret",
            "session_token": "tok",
            "base_url": "https://so.example.com",
        },
        account_id="11111111-1111-1111-1111-111111111111",
    )
    assert client._ctx.transport.session_token == "tok"
    assert client._ctx.transport.data_plane_bases.get("so") == "https://so.example.com"
    assert client.account_id() == "11111111-1111-1111-1111-111111111111"
    client.close()


def test_from_sts_mail_uses_mailapi_data_plane(monkeypatch) -> None:
    monkeypatch.delenv("HC_ACCOUNT_ID", raising=False)
    client = HomeCloud.from_sts(
        {
            "resource_type": "mail",
            "resource_name": "*",
            "access_key_id": "HCSAKMAIL",
            "secret_access_key": "secret",
            "session_token": "tok",
            "base_url": "https://mailapi.holab.abrdns.com",
        },
        account_id="11111111-1111-1111-1111-111111111111",
    )
    assert client._ctx.transport.data_plane_bases.get("mail") == "https://mailapi.holab.abrdns.com"
    assert client._ctx.transport.console_base_url is None
    client.close()

    monkeypatch.setenv("HC_ACCOUNT_ID", "22222222-2222-2222-2222-222222222222")
    ctx = {
        "account_id": "22222222-2222-2222-2222-222222222222",
        "sts": {
            "archive": {
                "resource_type": "so",
                "access_key_id": "HCSAK1",
                "secret_access_key": "s",
                "session_token": "t",
                "base_url": "https://so.holab.abrdns.com",
            }
        },
    }
    client = HomeCloud.from_function_context(ctx, binding="archive")
    assert client._ctx.transport.session_token == "t"
    client.close()
