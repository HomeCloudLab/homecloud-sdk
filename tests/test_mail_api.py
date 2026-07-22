"""MailAPI unit tests (JWT or Access Key plane)."""

from __future__ import annotations

from unittest.mock import MagicMock

from homecloud_sdk.services import MailAPI


def test_mail_get_message_and_attachment_via_access_key() -> None:
    ctx = MagicMock()
    ctx.has_access_key = True
    ctx.account_id.return_value = "acc-1"
    ctx.transport.console_signed_request.return_value = {
        "id": "msg-1",
        "subject": "Hi",
        "body_html": "<p>x</p>",
        "attachments": [{"part_id": "1", "filename": "a.txt"}],
    }
    ctx.transport.console_signed_request_bytes.return_value = b"file-bytes"

    api = MailAPI(ctx)
    detail = api.get_message("msg-1")
    assert detail["body_html"] == "<p>x</p>"
    ctx.transport.console_signed_request.assert_called_with(
        "GET",
        "accounts/acc-1/mail/messages/msg-1",
        "acc-1",
        params=None,
    )

    raw = api.download_attachment("msg-1", "1")
    assert raw == b"file-bytes"
    ctx.transport.console_signed_request_bytes.assert_called_with(
        "GET",
        "accounts/acc-1/mail/messages/msg-1/attachments/1",
        "acc-1",
    )


def test_mail_list_mailboxes_via_jwt() -> None:
    ctx = MagicMock()
    ctx.has_access_key = False
    ctx.account_id.return_value = "acc-1"
    ctx.transport.console_request.return_value = {"items": [{"email": "a@b.com"}]}
    api = MailAPI(ctx)
    items = api.list_mailboxes()
    assert items[0]["email"] == "a@b.com"
    ctx.require_console_session.assert_called()
