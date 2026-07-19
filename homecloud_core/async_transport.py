"""Async HTTP transport — mirror of Transport with httpx.AsyncClient."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from homecloud_core.defaults import WHOAMI_ACCOUNT_SENTINEL, WHOAMI_PATH, so_url
from homecloud_core.errors import HomeCloudError, NotLoggedInError
from homecloud_core.http_helpers import (
    MAX_RETRIES,
    RETRY_STATUS,
    Plane,
    console_request_url,
    error_from_failed_response,
    parse_response,
    require_access_key,
    signed_data_plane_url,
)
from homecloud_core.signing import sign_request_headers

__all__ = ["AsyncTransport", "Plane"]


class AsyncTransport:
    """Same surface as :class:`Transport`, but all I/O is async.

    Interactive MFA resolvers are not supported on the async path — pass a
    console JWT / Access Key already resolved outside the event loop.
    """

    def __init__(
        self,
        *,
        apex: str,
        access_key_id: str | None,
        secret_access_key: str | None,
        access_token: str | None,
        timeout: float = 30.0,
    ) -> None:
        self.apex = apex
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.access_token = access_token
        self.timeout = timeout
        self._http_client: httpx.AsyncClient | None = None
        self._http_lock = asyncio.Lock()

    async def _http(self) -> httpx.AsyncClient:
        async with self._http_lock:
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    limits=httpx.Limits(max_connections=100, max_keepalive_connections=32),
                )
            return self._http_client

    async def aclose(self) -> None:
        async with self._http_lock:
            if self._http_client is not None:
                await self._http_client.aclose()
                self._http_client = None

    async def console_request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        require_auth: bool = True,
    ) -> Any:
        if require_auth and not self.access_token:
            raise NotLoggedInError("Not logged in. Run: homecloud login")

        headers: dict[str, str] = {}
        if require_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        url = console_request_url(self.apex, path)
        return await self._request(method, url, headers=headers, json=json, params=params)

    async def data_plane_request_bytes(
        self,
        plane: Plane,
        method: str,
        path: str,
        account_id: str,
        *,
        url_path: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> bytes:
        require_access_key(self.access_key_id, self.secret_access_key)
        assert self.access_key_id and self.secret_access_key
        url, headers = signed_data_plane_url(
            apex=self.apex,
            plane=plane,
            access_key_id=self.access_key_id,
            secret_access_key=self.secret_access_key,
            method=method,
            path=path,
            account_id=account_id,
            url_path=url_path,
        )
        last_error: HomeCloudError | None = None
        client = await self._http()
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.request(method, url, headers=headers, params=params)
            except httpx.HTTPError as exc:
                if attempt == MAX_RETRIES:
                    raise HomeCloudError(f"Request failed: {exc}") from exc
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code not in RETRY_STATUS or attempt == MAX_RETRIES:
                if response.is_success:
                    return response.content
                raise error_from_failed_response(response)
            last_error = HomeCloudError(
                f"Request failed ({response.status_code})",
                status_code=response.status_code,
            )
            await asyncio.sleep(0.5 * (attempt + 1))
        raise last_error or HomeCloudError("Request failed")

    async def data_plane_download_to_file(
        self,
        plane: Plane,
        path: str,
        account_id: str,
        dest: Path,
        *,
        url_path: str | None = None,
        params: dict[str, Any] | None = None,
        on_chunk: Callable[[int], None] | None = None,
    ) -> int:
        require_access_key(self.access_key_id, self.secret_access_key)
        assert self.access_key_id and self.secret_access_key
        dest.parent.mkdir(parents=True, exist_ok=True)

        url, headers = signed_data_plane_url(
            apex=self.apex,
            plane=plane,
            access_key_id=self.access_key_id,
            secret_access_key=self.secret_access_key,
            method="GET",
            path=path,
            account_id=account_id,
            url_path=url_path,
        )
        last_error: HomeCloudError | None = None
        client = await self._http()
        download_timeout = httpx.Timeout(30.0, read=None)
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with client.stream(
                    "GET",
                    url,
                    headers=headers,
                    params=params,
                    timeout=download_timeout,
                ) as response:
                    if response.status_code in RETRY_STATUS and attempt < MAX_RETRIES:
                        last_error = HomeCloudError(
                            f"Request failed ({response.status_code})",
                            status_code=response.status_code,
                        )
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue
                    if not response.is_success:
                        detail: Any
                        try:
                            body = await response.aread()
                            parsed = json.loads(body)
                            detail = parsed.get("detail", parsed)
                        except Exception:
                            detail = response.text or response.reason_phrase
                        raise HomeCloudError(
                            f"Request failed ({response.status_code})",
                            status_code=response.status_code,
                            detail=detail,
                        )

                    nbytes = 0
                    with dest.open("wb") as handle:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            handle.write(chunk)
                            chunk_len = len(chunk)
                            nbytes += chunk_len
                            if on_chunk is not None:
                                on_chunk(chunk_len)
                    return nbytes
            except HomeCloudError:
                raise
            except httpx.HTTPError as exc:
                if attempt == MAX_RETRIES:
                    raise HomeCloudError(f"Request failed: {exc}") from exc
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
        raise last_error or HomeCloudError("Request failed")

    async def data_plane_request(
        self,
        plane: Plane,
        method: str,
        path: str,
        account_id: str,
        *,
        url_path: str | None = None,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        require_access_key(self.access_key_id, self.secret_access_key)
        assert self.access_key_id and self.secret_access_key
        url, headers = signed_data_plane_url(
            apex=self.apex,
            plane=plane,
            access_key_id=self.access_key_id,
            secret_access_key=self.secret_access_key,
            method=method,
            path=path,
            account_id=account_id,
            url_path=url_path,
        )
        return await self._request(
            method,
            url,
            headers=headers,
            json=json,
            params=params,
            data=data,
            files=files,
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        last_error: HomeCloudError | None = None
        client = await self._http()
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=json,
                    params=params,
                    data=data,
                    files=files,
                )
            except httpx.HTTPError as exc:
                if attempt == MAX_RETRIES:
                    raise HomeCloudError(f"Request failed: {exc}") from exc
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            if response.status_code not in RETRY_STATUS or attempt == MAX_RETRIES:
                return parse_response(response)
            last_error = HomeCloudError(
                f"Request failed ({response.status_code})",
                status_code=response.status_code,
            )
            await asyncio.sleep(0.5 * (attempt + 1))
        raise last_error or HomeCloudError("Request failed")

    async def resolve_access_key_account_id(self) -> str:
        require_access_key(self.access_key_id, self.secret_access_key)
        assert self.access_key_id and self.secret_access_key

        headers = sign_request_headers(
            access_key_id=self.access_key_id,
            secret=self.secret_access_key,
            method="GET",
            path=WHOAMI_PATH,
            account_id=WHOAMI_ACCOUNT_SENTINEL,
        )
        url = f"{so_url(self.apex).rstrip('/')}{WHOAMI_PATH}"
        data = await self._request("GET", url, headers=headers)
        account_id = data.get("account_id")
        if not account_id:
            raise HomeCloudError("Could not resolve account from Access Key")
        return str(account_id)
