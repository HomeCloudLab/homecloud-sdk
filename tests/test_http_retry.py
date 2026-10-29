"""HTTP retry helper tests."""

from __future__ import annotations

import httpx

from homecloud_core.http_helpers import RETRY_STATUS, retry_delay_seconds


def test_retry_status_includes_429() -> None:
    assert 429 in RETRY_STATUS


def test_retry_delay_honors_retry_after_on_429() -> None:
    request = httpx.Request("GET", "https://example.test/")
    response = httpx.Response(429, headers={"Retry-After": "2.5"}, request=request)
    assert retry_delay_seconds(response, 0) == 2.5


def test_retry_delay_caps_retry_after() -> None:
    request = httpx.Request("GET", "https://example.test/")
    response = httpx.Response(429, headers={"Retry-After": "9999"}, request=request)
    assert retry_delay_seconds(response, 0) == 120.0


def test_retry_delay_default_backoff_without_header() -> None:
    request = httpx.Request("GET", "https://example.test/")
    response = httpx.Response(503, request=request)
    assert retry_delay_seconds(response, 1) == 1.0
