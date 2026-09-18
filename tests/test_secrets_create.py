"""SecretsAPI create / put payload tests."""

from __future__ import annotations

from unittest.mock import MagicMock

from homecloud_sdk.services import SecretsAPI


def test_secrets_create_empty_shell_access_key() -> None:
    ctx = MagicMock()
    ctx.has_access_key = True
    ctx.account_id.return_value = "acc-1"
    ctx.transport.console_signed_request.return_value = {"name": "my-secret", "status": "active"}
    api = SecretsAPI(ctx)
    created = api.create("my-secret", description="demo")
    assert created["name"] == "my-secret"
    ctx.require_console_session.assert_not_called()
    ctx.transport.console_signed_request.assert_called_once_with(
        "POST",
        "accounts/acc-1/secrets",
        "acc-1",
        json={"name": "my-secret", "description": "demo"},
    )


def test_secrets_create_with_field_kwargs_seeds_via_put_value() -> None:
    ctx = MagicMock()
    ctx.has_access_key = True
    ctx.account_id.return_value = "acc-1"
    ctx.transport.console_signed_request.return_value = {"name": "my-secret", "status": "active"}
    ctx.transport.data_plane_request.return_value = {"name": "my-secret", "version": 1}
    api = SecretsAPI(ctx)
    result = api.create("my-secret", API_KEY="test")
    assert result["version"] == 1
    ctx.transport.console_signed_request.assert_called_once()
    ctx.transport.data_plane_request.assert_called_once()
    call = ctx.transport.data_plane_request.call_args
    assert call.args[0] == "secrets"
    assert call.args[1] == "PUT"
    assert call.kwargs["json"] == {"values": {"API_KEY": "test"}}


def test_secrets_create_jwt_fallback() -> None:
    ctx = MagicMock()
    ctx.has_access_key = False
    ctx.account_id.return_value = "acc-1"
    ctx.transport.console_request.return_value = {"name": "s1"}
    api = SecretsAPI(ctx)
    api.create("s1")
    ctx.require_console_session.assert_called()
    ctx.transport.console_request.assert_called_once_with(
        "POST",
        "accounts/acc-1/secrets",
        json={"name": "s1"},
    )
