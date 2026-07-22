"""MailAPI unit tests (console JWT plane)."""

from __future__ import annotations

from unittest.mock import MagicMock

from homecloud_sdk.services import MailAPI


def test_mail_get_message_and_attachment() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.transport.console_request.return_value = {
        "id": "msg-1",
        "subject": "Hi",
        "body_html": "<p>x</p>",
        "attachments": [{"part_id": "1", "filename": "a.txt"}],
    }
    ctx.transport.console_request_bytes.return_value = b"file-bytes"

    api = MailAPI(ctx)
    detail = api.get_message("msg-1")
    assert detail["body_html"] == "<p>x</p>"
    ctx.transport.console_request.assert_called_with(
        "GET",
        "accounts/acc-1/mail/messages/msg-1",
    )

    raw = api.download_attachment("msg-1", "1")
    assert raw == b"file-bytes"
    ctx.transport.console_request_bytes.assert_called_with(
        "GET",
        "accounts/acc-1/mail/messages/msg-1/attachments/1",
    )


def test_mail_list_mailboxes() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.transport.console_request.return_value = {"items": [{"email": "a@b.com"}]}
    api = MailAPI(ctx)
    items = api.list_mailboxes()
    assert items[0]["email"] == "a@b.com"
