"""SO path / URI helpers."""

import pytest

from homecloud_core.so_paths import (
    format_so_uri,
    is_so_uri,
    parse_so_uri,
    sync_join_prefix,
    sync_relative_local_path,
)


def test_is_so_uri() -> None:
    assert is_so_uri("so://bucket/")
    assert is_so_uri("s3://bucket/key")
    assert is_so_uri("SO://Bucket/a")
    assert not is_so_uri("./local")
    assert not is_so_uri("bucket/key")


def test_parse_so_uri() -> None:
    assert parse_so_uri("so://docs/") == ("docs", "")
    assert parse_so_uri("so://docs/photos/") == ("docs", "photos")
    assert parse_so_uri("s3://a/b/c.txt") == ("a", "b/c.txt")


def test_parse_so_uri_requires_bucket() -> None:
    with pytest.raises(ValueError, match="bucket"):
        parse_so_uri("so://")


def test_format_so_uri() -> None:
    assert format_so_uri("docs") == "so://docs/"
    assert format_so_uri("docs", "photos/") == "so://docs/photos/"


def test_sync_join_and_relative() -> None:
    assert sync_join_prefix("photos", "a.txt") == "photos/a.txt"
    assert sync_join_prefix("", "a.txt") == "a.txt"
    assert sync_relative_local_path("photos/a.txt", "photos") == "a.txt"
    assert sync_relative_local_path("photos/a.txt", "") == "photos/a.txt"
