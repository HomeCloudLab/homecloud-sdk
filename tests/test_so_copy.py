from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from homecloud_sdk.services import SoAPI


def test_copy_posts_to_copy_endpoint() -> None:
    ctx = MagicMock()
    ctx.account_id.return_value = "100000000001"
    so = SoAPI(ctx)
    recorded: dict[str, Any] = {}

    def capture(service: str, method: str, path: str, account_id: str, **kwargs: Any) -> dict[str, Any]:
        recorded["service"] = service
        recorded["method"] = method
        recorded["path"] = path
        recorded["url_path"] = kwargs.get("url_path")
        recorded["json"] = kwargs.get("json")
        return {"key": "dest.txt"}

    ctx.transport.data_plane_request = capture
    result = so.copy("dest-b", "src.txt", "folder/dest.txt", source_bucket="src-b")
    assert result["key"] == "dest.txt"
    assert recorded["method"] == "POST"
    assert str(recorded["path"]).endswith("/copy")
    assert recorded["json"]["destination_key"] == "folder/dest.txt"
    assert recorded["json"]["source_bucket"] == "src-b"
