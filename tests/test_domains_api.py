"""DomainsAPI unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homecloud_sdk.async_services import AsyncDomainsAPI
from homecloud_sdk.services import DomainsAPI


def test_domains_list_create_records_attach() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.transport.console_request.side_effect = [
        {"items": [{"id": "d1", "fqdn": "example.com"}]},
        {"id": "d1", "fqdn": "example.com", "dns_mode": "homecloud"},
        {"items": [{"id": "r1", "type": "TXT"}]},
        {"id": "rec1", "type": "A", "host": "www"},
        {"zone_file": "$ORIGIN example.com.\n"},
        None,
        {"id": "a1", "fqdn": "www.example.com"},
    ]
    api = DomainsAPI(ctx)
    assert api.list()[0]["fqdn"] == "example.com"
    created = api.create("example.com", dns_mode="homecloud")
    assert created["id"] == "d1"
    assert api.list_records("d1")[0]["type"] == "TXT"
    record = api.create_record("d1", record_type="A", record="1.2.3.4", host="www")
    assert record["host"] == "www"
    assert api.export_zone("d1").startswith("$ORIGIN")
    api.delete_record("d1", "rec1")
    attached = api.attach("d1", target_id="fn-1", target_type="function", host="www")
    assert attached["fqdn"] == "www.example.com"
    ctx.transport.console_request.assert_any_call(
        "POST",
        "accounts/acc-1/domains/d1/dns-records",
        json={"type": "A", "record": "1.2.3.4", "host": "www", "ttl": 300},
    )
    ctx.transport.console_request.assert_any_call(
        "POST",
        "accounts/acc-1/domain-attachments",
        json={
            "domain_id": "d1",
            "target_id": "fn-1",
            "target_type": "function",
            "host": "www",
        },
    )
    ctx.transport.console_request.assert_any_call(
        "DELETE",
        "accounts/acc-1/domains/d1/dns-records/rec1",
    )


@pytest.mark.asyncio
async def test_async_domains_create_record_and_attach() -> None:
    ctx = MagicMock()
    ctx.account_id = AsyncMock(return_value="acc-1")
    ctx.transport.console_request = AsyncMock(
        side_effect=[
            {"id": "d1", "dns_mode": "homecloud"},
            {"id": "rec1", "type": "TXT"},
            {"id": "a1", "fqdn": "www.example.com"},
        ]
    )
    api = AsyncDomainsAPI(ctx)
    created = await api.create("example.com", dns_mode="homecloud")
    assert created["id"] == "d1"
    record = await api.create_record("d1", record_type="TXT", record="ok", host="_verify")
    assert record["type"] == "TXT"
    attached = await api.attach("d1", target_id="fn-1", target_type="function", host="www")
    assert attached["fqdn"] == "www.example.com"
    ctx.transport.console_request.assert_any_call(
        "POST",
        "accounts/acc-1/domain-attachments",
        json={
            "domain_id": "d1",
            "target_id": "fn-1",
            "target_type": "function",
            "host": "www",
        },
    )
