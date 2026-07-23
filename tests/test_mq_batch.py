from __future__ import annotations

import pytest

from homecloud_core.errors import HomeCloudError
from homecloud_sdk.mq_helpers import build_mq_batch_entries


def test_build_mq_batch_entries_payloads() -> None:
    entries = build_mq_batch_entries([{"a": 1}, "plain"])
    assert entries[0] == {"id": "0", "body": '{"a": 1}'}
    assert entries[1] == {"id": "1", "body": "plain"}


def test_build_mq_batch_entries_explicit() -> None:
    entries = build_mq_batch_entries(
        [{"id": "x", "body": "hello", "headers": {"k": "v"}}, {"body": "world"}]
    )
    assert entries[0] == {"id": "x", "body": "hello", "headers": {"k": "v"}}
    assert entries[1] == {"id": "1", "body": "world"}


def test_build_mq_batch_entries_rejects_empty() -> None:
    with pytest.raises(HomeCloudError, match="1–10"):
        build_mq_batch_entries([])


def test_build_mq_batch_entries_rejects_over_limit() -> None:
    with pytest.raises(HomeCloudError, match="1–10"):
        build_mq_batch_entries([{"i": i} for i in range(11)])


def test_build_mq_batch_entries_unique_ids() -> None:
    with pytest.raises(HomeCloudError, match="unique"):
        build_mq_batch_entries([{"id": "a", "body": "1"}, {"id": "a", "body": "2"}])
