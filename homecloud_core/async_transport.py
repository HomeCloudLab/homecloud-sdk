"""Async HTTP transport — mirror of Transport with httpx.AsyncClient."""

from __future__ import annotations

import asyncio
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
        self._signed_account_id: str | None = None

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

    async def _account_id_for_signing(self) -> str:
        if self._signed_account_id:
            return self._signed_account_id
        self._signed_account_id = await self.resolve_access_key_account_id()
        return self._signed_account_id

    async def console_request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        require_auth: bool = True,
    ) -> Any:
        if require_auth and self.access_key_id and self.secret_access_key:
            return await self.console_signed_request(
                method,
                path,
                await self._account_id_for_signing(),
                json=json,
                params=params,
            )
        if require_auth and not self.access_token:
            raise NotLoggedInError("Not logged in. Run: homecloud login")

        headers: dict[str, str] = {}
        if require_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        url = console_request_url(self.apex, path)
        return await self._request(method, url, headers=headers, json=json, params=params)

    async def console_sse_events(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ):
        """Yield parsed SSE ``data:`` JSON payloads (management plane)."""
        import json as _json

        rel = path.lstrip("/")
        headers: dict[str, str] = {"Accept": "text/event-stream"}
        if self.access_key_id and self.secret_access_key:
            require_access_key(self.access_key_id, self.secret_access_key)
            account_id = await self._account_id_for_signing()
            sign_path = f"/api/v1/{rel}"
            headers.update(
                sign_request_headers(
                    access_key_id=self.access_key_id,
                    secret=self.secret_access_key,
                    method="GET",
                    path=sign_path,
                    account_id=account_id,
                )
            )
        elif self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        else:
            raise NotLoggedInError("Not logged in. Run: homecloud login")

        url = console_request_url(self.apex, rel)
        stream_timeout = httpx.Timeout(
            None,
            connect=10.0,
            read=timeout if timeout is not None else max(self.timeout, 600.0),
            write=30.0,
            pool=10.0,
        )
        client = await self._http()
        async with client.stream(
            "GET", url, headers=headers, params=params, timeout=stream_timeout
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                raise HomeCloudError(
                    f"SSE request failed ({response.status_code}): {body[:500]!r}",
                    status_code=response.status_code,
                )
            event_name = "message"
            data_lines: list[str] = []
            async for raw_line in response.aiter_lines():
                line = raw_line
                if line == "":
                    if data_lines:
                        payload = "\n".join(data_lines)
                        data_lines = []
                        try:
                            obj = _json.loads(payload)
                            if isinstance(obj, dict):
                                if "type" not in obj and event_name and event_name != "message":
                                    obj = {**obj, "type": event_name}
                                yield obj
                        except Exception:
                            pass
                    event_name = "message"
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event_name = line[6:].strip() or "message"
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())

    async def console_request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        require_auth: bool = True,
    ) -> bytes:
        if require_auth and self.access_key_id and self.secret_access_key:
            rel = path.lstrip("/")
            sign_path = f"/api/v1/{rel}"
            require_access_key(self.access_key_id, self.secret_access_key)
            assert self.access_key_id and self.secret_access_key
            account_id = await self._account_id_for_signing()
            headers = sign_request_headers(
                access_key_id=self.access_key_id,
                secret=self.secret_access_key,
                method=method,
                path=sign_path,
                account_id=account_id,
            )
            url = console_request_url(self.apex, rel)
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
        if require_auth and not self.access_token:
            raise NotLoggedInError("Not logged in. Run: homecloud login")

        headers: dict[str, str] = {}
        if require_auth and self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        url = console_request_url(self.apex, path)
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

    async def console_signed_request(
        self,
        method: str,
        path: str,
        account_id: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Console API with Access Key SigV1 — management helpers without JWT."""
        require_access_key(self.access_key_id, self.secret_access_key)
        assert self.access_key_id and self.secret_access_key
        rel = path.lstrip("/")
        sign_path = f"/api/v1/{rel}"
        headers = sign_request_headers(
            access_key_id=self.access_key_id,
            secret=self.secret_access_key,
            method=method,
            path=sign_path,
            account_id=account_id,
        )
        url = console_request_url(self.apex, rel)
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
                        try:
                            await response.aread()
                        except Exception:
                            pass
                        raise error_from_failed_response(response)

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

    async def function_url_request(
        self,
        function_name: str,
        account_id: str,
        *,
        json: Any | None = None,
    ) -> Any:
        from homecloud_core.defaults import function_url

        require_access_key(self.access_key_id, self.secret_access_key)
        assert self.access_key_id and self.secret_access_key
        path = "/"
        headers = sign_request_headers(
            access_key_id=self.access_key_id,
            secret=self.secret_access_key,
            method="POST",
            path=path,
            account_id=account_id,
        )
        url = function_url(function_name, self.apex).rstrip("/") + "/"
        return await self._request("POST", url, headers=headers, json=json or {})

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
