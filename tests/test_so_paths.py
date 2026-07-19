from __future__ import annotations

from homecloud_core.so_paths import encode_object_key_path, so_object_paths, sync_relative_local_path


def test_encode_object_key_path_spaces() -> None:
    assert encode_object_key_path("docs/my file.txt") == "docs/my%20file.txt"


def test_so_object_paths() -> None:
    sign, url = so_object_paths("acc", "bucket", "a/b c.txt")
    assert sign == "/acc/bucket/objects/a/b c.txt"
    assert url == "/acc/bucket/objects/a/b%20c.txt"


def test_sync_relative_local_path() -> None:
    assert sync_relative_local_path("backup/a.txt", "backup") == "a.txt"
    assert sync_relative_local_path("backup", "backup") == "backup"
    assert sync_relative_local_path("other/x", "backup") == "other/x"
