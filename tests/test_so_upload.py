from __future__ import annotations

from io import BytesIO
from pathlib import Path

import httpx
import pytest

from homecloud_sdk import HomeCloud, HomeCloudError


def _mock_client(monkeypatch: pytest.MonkeyPatch, captured: dict):
    class MockHttpClient:
        def __init__(self, *args, **kwargs):
            pass

        def close(self) -> None:
            return None

        def request(self, method: str, url: str, **kwargs):
            request = httpx.Request(method, url, headers=kwargs.get("headers"))
            if request.url.path == "/access-key/whoami":
                return httpx.Response(200, json={"account_id": "acc-1"}, request=request)
            captured["method"] = method
            captured["path"] = request.url.path
            captured["data"] = kwargs.get("data")
            files = kwargs.get("files") or {}
            file_part = files.get("file")
            if file_part is not None:
                filename, stream, mime = file_part
                captured["filename"] = filename
                captured["mime"] = mime
                captured["file_bytes"] = stream.read() if hasattr(stream, "read") else stream
            return httpx.Response(
                201,
                json={"key": "videos/clip.mp4", "size": 4, "etag": "x"},
                request=request,
            )

    monkeypatch.setattr("homecloud_core.transport.httpx.Client", MockHttpClient)


def test_upload_body_with_content_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    captured: dict = {}
    _mock_client(monkeypatch, captured)

    client = HomeCloud(access_key="HCAK1", secret_key="sec", apex="example.test")
    client.so.upload(
        "bucket",
        body=b"data",
        key="videos/clip.mp4",
        content_type="video/mp4",
    )
    client.close()

    assert captured["method"] == "POST"
    assert captured["path"].endswith("/bucket/objects")
    assert captured["data"] == {"key": "videos/clip.mp4"}
    assert captured["filename"] == "clip.mp4"
    assert captured["mime"] == "video/mp4"
    assert captured["file_bytes"] == b"data"


def test_upload_body_guesses_mime_from_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    captured: dict = {}
    _mock_client(monkeypatch, captured)

    client = HomeCloud(access_key="HCAK1", secret_key="sec", apex="example.test")
    client.so.upload("bucket", body=BytesIO(b"{}"), key="a.json")
    client.close()

    assert captured["mime"] == "application/json"
    assert captured["file_bytes"] == b"{}"


def test_upload_file_path_with_content_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    captured: dict = {}
    _mock_client(monkeypatch, captured)
    src = tmp_path / "note.txt"
    src.write_bytes(b"hi")

    client = HomeCloud(access_key="HCAK1", secret_key="sec", apex="example.test")
    client.so.upload("bucket", str(src), key="docs/note.txt", content_type="text/plain")
    client.close()

    assert captured["filename"] == "note.txt"
    assert captured["mime"] == "text/plain"
    assert captured["data"] == {"key": "docs/note.txt"}
    assert captured["file_bytes"] == b"hi"


def test_upload_body_requires_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    client = HomeCloud(access_key="HCAK1", secret_key="sec", apex="example.test")
    with pytest.raises(HomeCloudError, match="key is required"):
        client.so.upload("bucket", body=b"x")
    client.close()


def test_upload_rejects_both_path_and_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOMECLOUD_CONFIG_DIR", str(tmp_path))
    src = tmp_path / "a.bin"
    src.write_bytes(b"x")
    client = HomeCloud(access_key="HCAK1", secret_key="sec", apex="example.test")
    with pytest.raises(HomeCloudError, match="not both"):
        client.so.upload("bucket", str(src), body=b"x", key="a.bin")
    client.close()
