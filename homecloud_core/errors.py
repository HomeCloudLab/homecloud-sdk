from __future__ import annotations

from typing import Any
from urllib.parse import unquote, urlparse


class HomeCloudError(Exception):
    """Base error for all HomeCloud SDK failures."""

    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail

    @property
    def error_payload(self) -> dict[str, Any] | None:
        """Normalized `{code, message, details}` from either envelope or legacy detail dict."""
        if not isinstance(self.detail, dict):
            return None
        error = self.detail.get("error")
        if isinstance(error, dict) and error.get("code"):
            details = error.get("details") if isinstance(error.get("details"), dict) else {}
            return {
                "code": str(error.get("code")),
                "message": str(error.get("message") or error.get("code")),
                "details": details,
            }
        if self.detail.get("code"):
            details = {
                key: value
                for key, value in self.detail.items()
                if key not in {"code", "message"}
            }
            return {
                "code": str(self.detail.get("code")),
                "message": str(self.detail.get("message") or self.detail.get("code")),
                "details": details,
            }
        return None

    @property
    def error_code(self) -> str | None:
        payload = self.error_payload
        return payload["code"] if payload else None

    @property
    def error_details(self) -> dict[str, Any]:
        payload = self.error_payload
        if not payload:
            return {}
        return dict(payload.get("details") or {})


class NotConfiguredError(HomeCloudError):
    """Access Key / local profile is missing."""


class NotLoggedInError(HomeCloudError):
    """Console JWT required but not present."""


class ApiError(HomeCloudError):
    """HTTP API error that did not map to a more specific type."""


class BadRequestError(ApiError):
    """HTTP 400."""


class UnauthorizedError(ApiError):
    """HTTP 401 — invalid or missing credentials."""


class PermissionDeniedError(ApiError):
    """HTTP 403 — including MFA step-up when ``error_code == MFA_REQUIRED``."""


class NotFoundError(ApiError):
    """HTTP 404 — bucket, object, queue, or other resource missing."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = 404,
        detail: Any = None,
        resource_type: str | None = None,
        resource: str | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, detail=detail)
        self.resource_type = resource_type
        self.resource = resource


class ConflictError(ApiError):
    """HTTP 409."""


class RateLimitError(ApiError):
    """HTTP 429."""


class ServiceUnavailableError(ApiError):
    """HTTP 502 / 503 / 504."""


def _detail_message(detail: Any) -> str | None:
    if detail is None:
        return None
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, dict):
        payload_code = None
        error = detail.get("error")
        if isinstance(error, dict):
            msg = error.get("message") or error.get("code")
            if msg:
                return str(msg)
            payload_code = error.get("code")
        if detail.get("message"):
            return str(detail["message"])
        if detail.get("code"):
            return str(detail["code"])
        if payload_code:
            return str(payload_code)
    if isinstance(detail, list) and detail:
        parts = []
        for item in detail[:3]:
            if isinstance(item, dict) and item.get("msg"):
                parts.append(str(item["msg"]))
            else:
                parts.append(str(item))
        return "; ".join(parts)
    return None


def _resource_hint(url: str) -> tuple[str | None, str | None, str | None]:
    """Return ``(resource_type, resource, human_message_prefix)`` from a request URL."""
    path = unquote(urlparse(url).path)
    parts = [p for p in path.split("/") if p]
    # Data plane: /{account}/{name}/objects/... or /{account}/{queue}/messages
    if len(parts) >= 3:
        name = parts[1]
        kind = parts[2]
        if kind == "objects":
            key_parts = parts[3:]
            while key_parts and key_parts[-1] in {
                "metadata",
                "uri",
                "presigned",
                "tags",
            }:
                key_parts = key_parts[:-1]
            # Strip multipart/... suffixes
            if "multipart" in key_parts:
                idx = key_parts.index("multipart")
                key_parts = key_parts[:idx]
            key = "/".join(key_parts)
            if key:
                return (
                    "object",
                    f"{name}/{key}",
                    f"Object not found: bucket={name!r} key={key!r}",
                )
            return "bucket", name, f"Bucket not found: {name!r}"
        if kind == "messages":
            return "queue", name, f"Queue not found: {name!r}"
    if "storage/buckets" in path:
        return "bucket", None, "Bucket not found"
    if "/queues" in path:
        return "queue", None, "Queue not found"
    if "/secrets" in path:
        return "secret", None, "Secret not found"
    return None, None, None


def error_from_status(
    status_code: int,
    *,
    detail: Any = None,
    url: str | None = None,
) -> HomeCloudError:
    """Map an HTTP failure to a typed :class:`HomeCloudError` subclass."""
    api_msg = _detail_message(detail)
    resource_type: str | None = None
    resource: str | None = None
    hint_msg: str | None = None
    if url:
        resource_type, resource, hint_msg = _resource_hint(url)

    if status_code == 400:
        return BadRequestError(
            api_msg or "Bad request",
            status_code=status_code,
            detail=detail,
        )
    if status_code == 401:
        return UnauthorizedError(
            api_msg or "Unauthorized — check Access Key or console session",
            status_code=status_code,
            detail=detail,
        )
    if status_code == 403:
        return PermissionDeniedError(
            api_msg or "Permission denied",
            status_code=status_code,
            detail=detail,
        )
    if status_code == 404:
        message = hint_msg or api_msg or "Resource not found"
        if hint_msg and api_msg and api_msg not in hint_msg:
            message = f"{hint_msg} ({api_msg})"
        return NotFoundError(
            message,
            status_code=status_code,
            detail=detail,
            resource_type=resource_type,
            resource=resource,
        )
    if status_code == 409:
        return ConflictError(
            api_msg or "Conflict",
            status_code=status_code,
            detail=detail,
        )
    if status_code == 429:
        return RateLimitError(
            api_msg or "Rate limit exceeded",
            status_code=status_code,
            detail=detail,
        )
    if status_code in {502, 503, 504}:
        return ServiceUnavailableError(
            api_msg or f"Service unavailable ({status_code})",
            status_code=status_code,
            detail=detail,
        )
    return ApiError(
        api_msg or f"Request failed ({status_code})",
        status_code=status_code,
        detail=detail,
    )
