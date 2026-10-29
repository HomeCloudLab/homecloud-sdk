"""TasksAPI and DiagramsAPI unit tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from homecloud_core.errors import HomeCloudError
from homecloud_sdk.async_services import AsyncDiagramsAPI, AsyncTasksAPI
from homecloud_sdk.services import DiagramsAPI, TasksAPI


def test_tasks_list_get_create_update_signed() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.has_access_key = True
    ctx.transport.console_signed_request.side_effect = [
        {"items": [{"key": "TASK-1", "title": "A"}], "total": 1},
        {"key": "TASK-1", "title": "A", "status": "open"},
        {"key": "TASK-2", "title": "New", "status": "open"},
        {"key": "TASK-2", "title": "New", "status": "in_progress"},
    ]
    api = TasksAPI(ctx)

    items = api.list(status="open", q="cert")
    assert items[0]["key"] == "TASK-1"
    assert api.get("TASK-1")["title"] == "A"
    created = api.create("New", type="change", priority="p2", label_names=["ops"])
    assert created["key"] == "TASK-2"
    updated = api.update("TASK-2", status="in_progress", clear_assignee=True)
    assert updated["status"] == "in_progress"

    ctx.transport.console_signed_request.assert_any_call(
        "GET",
        "accounts/acc-1/tasks/items",
        "acc-1",
        params={"archived": False, "status": "open", "q": "cert"},
    )


def test_tasks_resolve_user_and_assign() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.has_access_key = True
    alice_id = "11111111-1111-1111-1111-111111111111"
    me_id = "22222222-2222-2222-2222-222222222222"
    ctx.transport.console_signed_request.side_effect = [
        {"principal_id": me_id, "username": "root"},
        {"items": [{"id": alice_id, "username": "alice"}], "total": 1},
        {"key": "TASK-1", "status": "in_progress"},
        {"key": "TASK-1", "comment_id": "c1"},
        {"items": [{"event_type": "commented"}], "total": 1},
        {"key": "TASK-1", "archived": True},
    ]
    api = TasksAPI(ctx)
    assert api.resolve_user("me") == me_id
    ctx.transport.console_signed_request.assert_any_call(
        "GET", "access-key/whoami", "-"
    )
    assert api.resolve_user("@alice") == alice_id
    api.assign_me("TASK-1", status="in_progress")
    api.comment("TASK-1", "hello")
    assert api.activity("TASK-1")[0]["event_type"] == "commented"
    api.archive("TASK-1", cancel=True)
    ctx.transport.console_signed_request.assert_any_call(
        "PATCH",
        "accounts/acc-1/tasks/items/TASK-1",
        "acc-1",
        json={"assignee_user_ids": [me_id], "status": "in_progress"},
    )


def test_tasks_resolve_unknown_user() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.has_access_key = True
    ctx.transport.console_signed_request.return_value = {"items": [], "total": 0}
    api = TasksAPI(ctx)
    with pytest.raises(HomeCloudError, match="Unknown user"):
        api.resolve_user("nobody")


def test_tasks_list_page_and_upsert_bulk_relations() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.has_access_key = True
    ctx.transport.console_signed_request.side_effect = [
        {"items": [{"key": "TASK-1", "id": "id-1"}], "total": 1, "next_cursor": "c2"},
        {"items": [{"key": "TASK-2", "id": "id-2"}], "total": 2, "next_cursor": None},
        {"items": [{"key": "TASK-1", "id": "id-1"}], "total": 1, "next_cursor": "c2"},
        {"key": "TASK-9", "external_id": "ext-1", "title": "Upserted"},
        {"results": [], "created": 1, "failed": 0},
        {"results": [], "created": 1, "failed": 0},
        {"id": "rel-1", "relation_type": "blocks", "from_key": "TASK-1", "to_key": "TASK-2"},
        {"items": [{"id": "rel-1"}], "total": 1},
        None,
    ]
    api = TasksAPI(ctx)

    all_items = api.list_all(status="open")
    assert {i["key"] for i in all_items} == {"TASK-1", "TASK-2"}
    page = api.list_page(status="open", limit=50, sort="-sequence", external_id="ext-1")
    assert page["next_cursor"] == "c2"

    upserted = api.upsert_by_external("ext-1", title="Upserted")
    assert upserted["key"] == "TASK-9"
    api.bulk_create([{"title": "A"}])
    api.bulk_delete(["TASK-1"])
    rel = api.link_relation("TASK-1", "TASK-2", "blocks")
    assert rel["id"] == "rel-1"
    assert api.list_relations("TASK-1")[0]["id"] == "rel-1"
    api.unlink_relation("TASK-1", "rel-1")

    ctx.transport.console_signed_request.assert_any_call(
        "PUT",
        "accounts/acc-1/tasks/items/by-external/ext-1",
        "acc-1",
        json={"title": "Upserted"},
    )


def test_tasks_jwt_fallback() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.has_access_key = False
    ctx.transport.console_request.return_value = {"items": [], "total": 0}
    api = TasksAPI(ctx)
    assert api.list() == []
    ctx.require_console_session.assert_called_once()


def test_diagrams_list_get_create_update() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "acc-1"
    ctx.has_access_key = True
    ctx.transport.console_signed_request.side_effect = [
        {"items": [{"id": "d1", "name": "Plan"}], "total": 1},
        {"id": "d1", "name": "Plan", "document": {"nodes": []}, "revision": 1},
        {"id": "d2", "name": "Prod", "revision": 1},
        {"id": "d2", "name": "Prod v2", "revision": 2},
    ]
    api = DiagramsAPI(ctx)
    assert api.list()[0]["id"] == "d1"
    assert api.get("d1")["revision"] == 1
    created = api.create("Prod", description="draft")
    assert created["id"] == "d2"
    updated = api.update("d2", name="Prod v2", revision=1)
    assert updated["revision"] == 2


def test_async_tasks_and_diagrams() -> None:
    async def run() -> None:
        ctx = MagicMock()
        ctx.account_id = AsyncMock(return_value="acc-1")
        ctx.has_access_key = False
        ctx.transport.console_request = AsyncMock(
            side_effect=[
                {"items": [{"key": "TASK-1"}], "total": 1},
                {"key": "TASK-1", "title": "A"},
                {"items": [{"id": "d1"}], "total": 1},
                {"id": "d1", "name": "Plan", "revision": 1},
            ]
        )
        tasks = AsyncTasksAPI(ctx)
        assert (await tasks.list())[0]["key"] == "TASK-1"
        assert (await tasks.get("TASK-1"))["title"] == "A"
        diagrams = AsyncDiagramsAPI(ctx)
        assert (await diagrams.list())[0]["id"] == "d1"
        assert (await diagrams.get("d1"))["name"] == "Plan"

    asyncio.run(run())
