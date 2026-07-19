"""Typed HTTP error mapping."""

from __future__ import annotations

import httpx

from homecloud_core.errors import (
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
    error_from_status,
)
from homecloud_core.http_helpers import error_from_failed_response, parse_response


def test_error_from_status_object_not_found() -> None:
    err = error_from_status(
        404,
        detail={"message": "NoSuchKey"},
        url="https://so.example.test/acc/docs/objects/a.txt/metadata",
    )
    assert isinstance(err, NotFoundError)
    assert err.resource_type == "object"
    assert err.resource == "docs/a.txt"
    assert "docs" in str(err)
    assert "a.txt" in str(err)


def test_error_from_status_queue_not_found() -> None:
    err = error_from_status(
        404,
        url="https://mq.example.test/acc/orders/messages",
    )
    assert isinstance(err, NotFoundError)
    assert err.resource_type == "queue"
    assert err.resource == "orders"


def test_error_from_status_auth() -> None:
    assert isinstance(error_from_status(401), UnauthorizedError)
    assert isinstance(error_from_status(403, detail={"error": {"code": "MFA_REQUIRED"}}), PermissionDeniedError)
    assert error_from_status(403, detail={"error": {"code": "MFA_REQUIRED"}}).error_code == "MFA_REQUIRED"


def test_parse_response_raises_not_found() -> None:
    request = httpx.Request("GET", "https://so.example.test/acc/bucket/objects/missing.txt/metadata")
    response = httpx.Response(404, json={"detail": "not found"}, request=request)
    try:
        parse_response(response)
        raise AssertionError("expected NotFoundError")
    except NotFoundError as exc:
        assert exc.status_code == 404
        assert exc.resource_type == "object"


def test_error_from_failed_response_typed() -> None:
    request = httpx.Request("GET", "https://mq.example.test/acc/q1/messages")
    response = httpx.Response(404, text="missing", request=request)
    err = error_from_failed_response(response)
    assert isinstance(err, NotFoundError)
    assert err.resource_type == "queue"
