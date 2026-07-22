"""Shared HTTP helpers for sync and async transports."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urljoin

import httpx

from homecloud_core.defaults import mail_api_url, mq_url, secrets_url, so_url
from homecloud_core.errors import HomeCloudError, error_from_status
from homecloud_core.signing import sign_request_headers

Plane = Literal["console", "mq", "so", "secrets", "mail"]

MAX_RETRIES = 2
RETRY_STATUS = {502, 503, 504}


def require_access_key(access_key_id: str | None, secret_access_key: str | None) -> None:
    if not access_key_id or not secret_access_key:
        raise HomeCloudError(
            "Access Key not configured. "
            "Run: homecloud configure, or set HOMECLOUD_ACCESS_KEY_ID / HC_ACCESS_KEY_ID"
        )


def data_plane_base_urls(apex: str) -> dict[str, str]:
    return {
        "mq": mq_url(apex),
        "so": so_url(apex),
        "secrets": secrets_url(apex),
        "mail": mail_api_url(apex),
    }


def signed_data_plane_url(
    *,
    apex: str,
    plane: Plane,
    access_key_id: str,
    secret_access_key: str,
    method: str,
    path: str,
    account_id: str,
    url_path: str | None = None,
    session_token: str | None = None,
    base_url_override: str | None = None,
) -> tuple[str, dict[str, str]]:
    require_access_key(access_key_id, secret_access_key)
    base = (base_url_override or data_plane_base_urls(apex)[plane]).rstrip("/")
    headers = sign_request_headers(
        access_key_id=access_key_id,
        secret=secret_access_key,
        method=method,
        path=path,
        account_id=account_id,
        session_token=session_token,
    )
    url = f"{base}{url_path or path}"
    return url, headers


def console_request_url(apex: str, path: str) -> str:
    from homecloud_core.defaults import console_url

    return urljoin(console_url(apex).rstrip("/") + "/", path.lstrip("/"))


def _response_url(response: httpx.Response) -> str:
    try:
        return str(response.request.url)
    except RuntimeError:
        return ""


def _response_detail(response: httpx.Response) -> Any:
    try:
        body = response.json()
        return body.get("detail", body)
    except Exception:
        return response.text


def parse_response(response: httpx.Response) -> Any:
    if response.is_success:
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise HomeCloudError(
                f"Invalid JSON response ({response.status_code}) from {_response_url(response) or 'unknown'}",
                status_code=response.status_code,
            ) from exc

    raise error_from_status(
        response.status_code,
        detail=_response_detail(response),
        url=_response_url(response),
    )


def error_from_failed_response(response: httpx.Response) -> HomeCloudError:
    return error_from_status(
        response.status_code,
        detail=_response_detail(response),
        url=_response_url(response),
    )
