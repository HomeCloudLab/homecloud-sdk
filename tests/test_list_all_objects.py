"""Regression: SO list returns pages=null + has_more (honest pagination)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from homecloud_sdk.services import SoAPI


def test_list_all_objects_tolerates_null_pages() -> None:
    so = SoAPI(MagicMock())
    calls: list[dict[str, Any]] = []

    def fake_list(
        bucket_name: str,
        *,
        prefix: str = "",
        recursive: bool = False,
        page: int = 1,
        page_size: int = 100,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        calls.append({"page": page, "continuation_token": continuation_token})
        if continuation_token is None:
            return {
                "items": [{"key": "a.html", "size": 1, "is_dir": False}],
                "pages": None,
                "has_more": True,
                "next_continuation_token": "tok-1",
            }
        return {
            "items": [{"key": "b.html", "size": 2, "is_dir": False}],
            "pages": None,
            "has_more": False,
            "next_continuation_token": None,
        }

    so.list_objects = fake_list  # type: ignore[method-assign]
    items = so.list_all_objects("docs", prefix="", recursive=True)
    assert [i["key"] for i in items] == ["a.html", "b.html"]
    assert calls[0]["continuation_token"] is None
    assert calls[1]["continuation_token"] == "tok-1"


def test_list_all_objects_legacy_pages_field() -> None:
    so = SoAPI(MagicMock())
    pages_seen: list[int] = []

    def fake_list(
        bucket_name: str,
        *,
        prefix: str = "",
        recursive: bool = False,
        page: int = 1,
        page_size: int = 100,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        pages_seen.append(page)
        return {
            "items": [{"key": f"p{page}.html", "size": 1, "is_dir": False}],
            "pages": 2,
            "has_more": False,
            "next_continuation_token": None,
        }

    so.list_objects = fake_list  # type: ignore[method-assign]
    items = so.list_all_objects("docs")
    assert [i["key"] for i in items] == ["p1.html", "p2.html"]
    assert pages_seen == [1, 2]
