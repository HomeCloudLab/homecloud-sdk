"""ContainersAPI unit tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from homecloud_core.errors import NotLoggedInError
from homecloud_sdk.async_services import AsyncContainersAPI
from homecloud_sdk.services import ContainersAPI


def test_containers_list_create_tasks_logs() -> None:
    ctx = MagicMock()
    ctx.has_console_session = True
    ctx.account_id.return_value = "acc-1"
    ctx.transport.compute_request.side_effect = [
        {"items": [{"id": "svc-1", "name": "web", "status": "ACTIVE"}]},
        {
            "service": {"id": "svc-1", "name": "web"},
            "revision": {"id": "rev-1", "revision_number": 1},
            "operation_id": "op-1",
        },
        {"id": "svc-1", "name": "web", "status": "ACTIVE"},
        {"items": [{"id": "task-1", "observed_state": "RUNNING", "healthy": True}]},
        {"items": [{"ts": "2026-01-01T00:00:00Z", "stream": "stdout", "line": "ok"}]},
        {"operation_id": "op-del"},
    ]
    api = ContainersAPI(ctx)
    assert api.list_services()[0]["name"] == "web"
    created = api.create_service(name="web", region_code="eu-central", image="nginx:latest")
    assert created["service"]["id"] == "svc-1"
    assert api.get_service("svc-1")["status"] == "ACTIVE"
    assert api.list_tasks("svc-1")[0]["observed_state"] == "RUNNING"
    assert api.task_logs("task-1")[0]["line"] == "ok"
    deleted = api.delete_service("svc-1")
    assert deleted["operation_id"] == "op-del"
    ctx.transport.compute_request.assert_any_call(
        "POST",
        "accounts/acc-1/containers/services",
        json={
            "name": "web",
            "region_code": "eu-central",
            "image": "nginx:latest",
            "cpu_milli": 250,
            "memory_mib": 512,
            "desired_count": 1,
            "port": 80,
        },
    )


def test_containers_requires_jwt() -> None:
    ctx = MagicMock()
    ctx.has_console_session = False
    api = ContainersAPI(ctx)
    with pytest.raises(NotLoggedInError, match="homecloud login"):
        api.list_services()


def test_async_containers_create() -> None:
    async def run() -> None:
        ctx = MagicMock()
        ctx.has_console_session = True
        ctx.account_id = AsyncMock(return_value="acc-1")
        ctx.transport.compute_request = AsyncMock(
            return_value={"service": {"id": "svc-1"}, "operation_id": "op-1"}
        )
        api = AsyncContainersAPI(ctx)
        created = await api.create_service(
            name="api", region_code="eu-west", image="ghcr.io/acme/api@sha256:abc"
        )
        assert created["service"]["id"] == "svc-1"
        ctx.transport.compute_request.assert_awaited_once()

    asyncio.run(run())
