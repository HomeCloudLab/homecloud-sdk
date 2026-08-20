"""Async service APIs — thin facades over AsyncCoreContext."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from homecloud_core.async_context import AsyncCoreContext
from homecloud_core.errors import HomeCloudError
from homecloud_core.progress_reader import ProgressReader
from homecloud_core.so_paths import (
    format_so_uri,
    is_so_uri,
    parse_so_uri,
    so_object_paths,
    sync_join_prefix,
    sync_relative_local_path,
)
from homecloud_sdk.mq_helpers import build_mq_batch_entries
from homecloud_sdk.so_parallel import DEFAULT_SO_WORKERS
from homecloud_sdk.services import (
    UploadBody,
    _as_binary_stream,
    _resolve_upload_content_type,
)


async def _run_parallel_async(
    items: list[str],
    worker: Callable[[str], Awaitable[None]],
    *,
    max_workers: int = DEFAULT_SO_WORKERS,
) -> None:
    if not items:
        return
    workers = max(1, min(max_workers, len(items)))
    sem = asyncio.Semaphore(workers)
    errors: list[BaseException] = []

    async def guarded(item: str) -> None:
        async with sem:
            try:
                await worker(item)
            except BaseException as exc:
                errors.append(exc)

    await asyncio.gather(*(guarded(item) for item in items))
    if errors:
        raise errors[0]


class AsyncAccountsAPI:
    def __init__(self, ctx: AsyncCoreContext) -> None:
        self._ctx = ctx

    async def list(self) -> list[dict[str, Any]]:
        return await self._ctx.list_accounts()

    async def switch(self, account_ref: str) -> None:
        await self._ctx.switch_account(account_ref)


class AsyncQueuesAPI:
    def __init__(self, ctx: AsyncCoreContext) -> None:
        self._ctx = ctx

    async def list(self, *, live: bool = False) -> list[dict[str, Any]]:
        account_id = await self._ctx.account_id()
        params = {"live": "true"} if live else None
        path = f"accounts/{account_id}/queues"
        if self._ctx.has_access_key:
            data = await self._ctx.transport.console_signed_request(
                "GET", path, account_id, params=params
            )
            return data.get("items", [])
        self._ctx.require_console_session()
        data = await self._ctx.transport.console_request("GET", path, params=params)
        return data.get("items", [])

    async def get(self, queue_name: str) -> dict[str, Any]:
        account_id = await self._ctx.account_id()
        path = f"accounts/{account_id}/queues/{queue_name}"
        if self._ctx.has_access_key:
            return await self._ctx.transport.console_signed_request("GET", path, account_id)
        self._ctx.require_console_session()
        return await self._ctx.transport.console_request("GET", path)


class AsyncMqAPI:
    def __init__(self, ctx: AsyncCoreContext) -> None:
        self._ctx = ctx

    async def send(
        self,
        queue_name: str,
        body: dict[str, Any] | str | list[Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        if isinstance(body, list):
            if headers is not None:
                raise HomeCloudError("headers= is only supported for single mq.send, not batch")
            path = f"/{account_id}/{queue_name}/messages/batch"
            return await self._ctx.transport.data_plane_request(
                "mq",
                "POST",
                path,
                account_id,
                json={"entries": build_mq_batch_entries(body)},
            )
        path = f"/{account_id}/{queue_name}/messages"
        body_str = body if isinstance(body, str) else json.dumps(body)
        payload: dict[str, Any] = {"body": body_str}
        if headers:
            payload["headers"] = headers
        return await self._ctx.transport.data_plane_request(
            "mq",
            "POST",
            path,
            account_id,
            json=payload,
        )

    async def receive(
        self,
        queue_name: str,
        *,
        max_messages: int = 1,
        wait_seconds: int = 20,
        delete: bool = False,
    ) -> list[dict[str, Any]]:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        path = f"/{account_id}/{queue_name}/messages"
        params: dict[str, Any] = {"max_messages": max_messages, "wait_seconds": wait_seconds}
        if delete:
            params["delete"] = "true"
        data = await self._ctx.transport.data_plane_request(
            "mq",
            "GET",
            path,
            account_id,
            params=params,
        )
        return data.get("items", [])

    async def delete(self, queue_name: str, sequence: int) -> None:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        path = f"/{account_id}/{queue_name}/messages/{sequence}"
        await self._ctx.transport.data_plane_request("mq", "DELETE", path, account_id)

    async def purge(self, queue_name: str) -> None:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        path = f"/{account_id}/{queue_name}/purge"
        await self._ctx.transport.data_plane_request("mq", "POST", path, account_id)

    async def receive_dlq(
        self,
        queue_name: str,
        *,
        max_messages: int = 1,
        wait_seconds: int = 20,
        delete: bool = False,
    ) -> list[dict[str, Any]]:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        path = f"/{account_id}/{queue_name}/dlq/messages"
        params: dict[str, Any] = {"max_messages": max_messages, "wait_seconds": wait_seconds}
        if delete:
            params["delete"] = "true"
        data = await self._ctx.transport.data_plane_request(
            "mq",
            "GET",
            path,
            account_id,
            params=params,
        )
        return data.get("items", [])

    async def delete_dlq(self, queue_name: str, sequence: int) -> None:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        path = f"/{account_id}/{queue_name}/dlq/messages/{sequence}"
        await self._ctx.transport.data_plane_request("mq", "DELETE", path, account_id)

    async def purge_dlq(self, queue_name: str) -> None:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        path = f"/{account_id}/{queue_name}/dlq/purge"
        await self._ctx.transport.data_plane_request("mq", "POST", path, account_id)

class AsyncAppsAPI:
    def __init__(self, ctx: AsyncCoreContext) -> None:
        self._ctx = ctx

    async def list(self) -> list[dict[str, Any]]:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        data = await self._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/applications"
        )
        return data.get("items", [])


class AsyncSoAPI:
    """Object storage (SO) — async. Use ``client.so``."""

    def __init__(self, ctx: AsyncCoreContext) -> None:
        self._ctx = ctx

    async def list_buckets(self) -> list[dict[str, Any]]:
        """List buckets — Access Key preferred (Identity Reset Phase 2, no JWT needed).

        Falls back to the console JWT management endpoint when no Access Key is
        configured (interactive console sessions without `homecloud configure`).
        """
        if self._ctx.has_access_key:
            account_id = await self._ctx.account_id()
            data = await self._ctx.transport.data_plane_request(
                "so", "GET", f"/{account_id}/buckets", account_id
            )
            return data.get("items", [])
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        try:
            data = await self._ctx.transport.console_request(
                "GET", f"accounts/{account_id}/storage/buckets"
            )
        except HomeCloudError as exc:
            if exc.status_code in {401, 403}:
                raise HomeCloudError(
                    "list_buckets requires an Access Key or a valid console login. "
                    "Run: homecloud configure (or homecloud login).",
                    status_code=exc.status_code,
                    detail=exc.detail,
                ) from exc
            raise
        return data.get("items", [])

    async def create_bucket(self, name: str) -> dict[str, Any]:
        account_id = await self._ctx.account_id()
        path = f"accounts/{account_id}/storage/buckets"
        body = {"name": name.strip().lower()}
        if self._ctx.has_access_key:
            return await self._ctx.transport.console_signed_request(
                "POST", path, account_id, json=body
            )
        self._ctx.require_console_session()
        return await self._ctx.transport.console_request("POST", path, json=body)

    async def delete_bucket(self, name: str) -> None:
        account_id = await self._ctx.account_id()
        path = f"accounts/{account_id}/storage/buckets/{name.strip().lower()}"
        if self._ctx.has_access_key:
            await self._ctx.transport.console_signed_request("DELETE", path, account_id)
            return
        self._ctx.require_console_session()
        await self._ctx.transport.console_request("DELETE", path)

    async def list_objects(
        self,
        bucket_name: str,
        *,
        prefix: str = "",
        recursive: bool = False,
        page: int = 1,
        page_size: int = 100,
        continuation_token: str | None = None,
    ) -> dict[str, Any]:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        path = f"/{account_id}/{bucket_name}/objects"
        params: dict[str, Any] = {
            "prefix": prefix,
            "recursive": recursive,
            "page": page,
            "page_size": page_size,
        }
        if continuation_token:
            params["continuation_token"] = continuation_token
        return await self._ctx.transport.data_plane_request(
            "so",
            "GET",
            path,
            account_id,
            params=params,
        )

    async def upload(
        self,
        bucket_name: str,
        file_path: str | Path | None = None,
        *,
        body: UploadBody | None = None,
        key: str | None = None,
        content_type: str | None = None,
        on_bytes: Callable[[int], None] | None = None,
    ) -> dict[str, Any]:
        """Upload an object from a local path or in-memory body.

        Data plane — Access Key only. See sync ``SoAPI.upload``.
        """
        self._ctx.require_access_key()
        if body is not None and file_path is not None:
            raise HomeCloudError("Pass either file_path or body, not both")
        if body is None and file_path is None:
            raise HomeCloudError("file_path or body is required")
        if body is not None and (not key or not str(key).strip()):
            raise HomeCloudError("key is required when uploading body")

        account_id = await self._ctx.account_id()
        upload_path = f"/{account_id}/{bucket_name}/objects"

        if body is not None:
            object_key = str(key).strip().lstrip("/")
            filename = Path(object_key).name or "object"
            mime = _resolve_upload_content_type(
                content_type, object_key=object_key, filename=filename
            )
            stream, owns = _as_binary_stream(body)
            try:
                upload_body = (
                    ProgressReader(stream, on_bytes) if on_bytes is not None else stream
                )
                return await self._ctx.transport.data_plane_request(
                    "so",
                    "POST",
                    upload_path,
                    account_id,
                    data={"key": object_key},
                    files={"file": (filename, upload_body, mime)},
                )
            finally:
                if owns:
                    stream.close()

        path = Path(file_path)  # type: ignore[arg-type]
        if not path.is_file():
            raise HomeCloudError(f"File not found: {file_path}")

        object_key = key or path.name
        mime = _resolve_upload_content_type(
            content_type, object_key=object_key, filename=path.name
        )
        with path.open("rb") as handle:
            upload_body = (
                ProgressReader(handle, on_bytes) if on_bytes is not None else handle
            )
            return await self._ctx.transport.data_plane_request(
                "so",
                "POST",
                upload_path,
                account_id,
                data={"key": object_key},
                files={"file": (path.name, upload_body, mime)},
            )

    async def delete(self, bucket_name: str, object_key: str) -> None:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        sign_path, url_path = so_object_paths(account_id, bucket_name, object_key)
        await self._ctx.transport.data_plane_request(
            "so",
            "DELETE",
            sign_path,
            account_id,
            url_path=url_path,
        )

    async def copy(
        self,
        bucket_name: str,
        source_key: str,
        destination_key: str,
        *,
        source_bucket: str | None = None,
    ) -> dict[str, Any]:
        """Server-side copy into ``bucket_name`` (destination). Access Key."""
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        sign_path, url_path = so_object_paths(account_id, bucket_name, source_key)
        return await self._ctx.transport.data_plane_request(
            "so",
            "POST",
            f"{sign_path}/copy",
            account_id,
            url_path=f"{url_path}/copy",
            json={
                "destination_key": destination_key,
                "source_bucket": source_bucket,
            },
        )

    async def move(
        self,
        bucket_name: str,
        source_key: str,
        destination_key: str,
        *,
        source_bucket: str | None = None,
    ) -> dict[str, Any]:
        """Copy then delete source after verifying destination. Access Key."""
        src_bucket = source_bucket or bucket_name
        copied = await self.copy(
            bucket_name,
            source_key,
            destination_key,
            source_bucket=source_bucket,
        )
        await self.head_object(bucket_name, destination_key)
        await self.delete(src_bucket, source_key)
        return copied

    async def download(
        self,
        bucket_name: str,
        object_key: str,
        *,
        dest_path: str | Path,
        on_bytes: Callable[[int], None] | None = None,
    ) -> dict[str, Any]:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        key = object_key.lstrip("/")
        sign_path, url_path = so_object_paths(account_id, bucket_name, key)
        dest = Path(dest_path)
        nbytes = await self._ctx.transport.data_plane_download_to_file(
            "so",
            sign_path,
            account_id,
            dest,
            url_path=url_path,
            on_chunk=on_bytes,
        )
        return {"key": key, "size": nbytes, "path": str(dest)}

    async def head_object(self, bucket_name: str, object_key: str) -> dict[str, Any]:
        """Return object metadata only (no body) — Access Key data plane."""
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        key = object_key.lstrip("/")
        sign_path, url_path = so_object_paths(account_id, bucket_name, key)
        raw = await self._ctx.transport.data_plane_request(
            "so",
            "GET",
            f"{sign_path}/metadata",
            account_id,
            url_path=f"{url_path}/metadata",
        )
        if not isinstance(raw, dict):
            raise HomeCloudError("Invalid metadata response")
        user_meta = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        tags = raw.get("tags") if isinstance(raw.get("tags"), dict) else {}
        return {
            "key": str(raw.get("key") or key),
            "size": int(raw.get("size") or 0),
            "etag": raw.get("etag"),
            "content_type": raw.get("content_type"),
            "last_modified": raw.get("last_modified"),
            "metadata": {str(k): str(v) for k, v in user_meta.items()},
            "tags": {str(k): str(v) for k, v in tags.items()},
        }

    async def object_metadata(self, bucket_name: str, object_key: str) -> dict[str, Any]:
        return await self.head_object(bucket_name, object_key)

    async def get_object_uri(self, bucket_name: str, object_key: str) -> dict[str, Any]:
        """Return canonical object URIs (Access Key data plane)."""
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        key = object_key.lstrip("/")
        sign_path, url_path = so_object_paths(account_id, bucket_name, key)
        raw = await self._ctx.transport.data_plane_request(
            "so",
            "GET",
            f"{sign_path}/uri",
            account_id,
            url_path=f"{url_path}/uri",
        )
        if not isinstance(raw, dict):
            raise HomeCloudError("Invalid URI response")
        return {
            "so_uri": str(raw.get("so_uri") or f"so://{bucket_name}/{key}"),
            "https_url": str(raw.get("https_url") or ""),
            "https_requires_public": bool(raw.get("https_requires_public", True)),
        }

    async def generate_presigned_url(
        self,
        bucket_name: str,
        object_key: str,
        *,
        expires: int = 3600,
    ) -> dict[str, Any]:
        """Generate a time-limited GET URL for an object (Access Key data plane)."""
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        key = object_key.lstrip("/")
        sign_path, url_path = so_object_paths(account_id, bucket_name, key)
        raw = await self._ctx.transport.data_plane_request(
            "so",
            "GET",
            f"{sign_path}/presigned",
            account_id,
            url_path=f"{url_path}/presigned",
            params={"expires": expires},
        )
        if not isinstance(raw, dict) or not raw.get("url"):
            raise HomeCloudError("Invalid presigned URL response")
        return {
            "url": str(raw["url"]),
            "expires_in_seconds": int(raw.get("expires_in_seconds") or expires),
        }

    async def _remote_objects_for_sync(
        self,
        bucket_name: str,
        prefix_clean: str,
    ) -> dict[str, dict[str, Any]]:
        remote_items = await self.list_all_objects(
            bucket_name,
            prefix=prefix_clean,
            recursive=True,
        )
        remote_by_key = {item["key"]: item for item in remote_items}
        if not remote_by_key and prefix_clean and not prefix_clean.endswith("/"):
            try:
                meta = await self.object_metadata(bucket_name, prefix_clean)
            except HomeCloudError:
                return remote_by_key
            remote_by_key[prefix_clean] = {
                "key": prefix_clean,
                "size": int(meta.get("size") or 0),
                "is_dir": False,
            }
        return remote_by_key

    async def list_all_objects(
        self,
        bucket_name: str,
        *,
        prefix: str = "",
        recursive: bool = True,
        include_dirs: bool = False,
    ) -> list[dict[str, Any]]:
        """Page through SO list until exhausted (has_more / continuation token)."""
        items: list[dict[str, Any]] = []
        page = 1
        continuation_token: str | None = None
        while True:
            data = await self.list_objects(
                bucket_name,
                prefix=prefix,
                recursive=recursive,
                page=page,
                page_size=100,
                continuation_token=continuation_token,
            )
            for item in data.get("items", []):
                if not include_dirs and item.get("is_dir"):
                    continue
                items.append(item)
            next_token = data.get("next_continuation_token")
            if data.get("has_more") and next_token:
                continuation_token = str(next_token)
                page = 1
                continue
            pages = data.get("pages")
            if pages is not None and page < int(pages):
                page += 1
                continuation_token = None
                continue
            break
        return items

    async def delete_recursive(
        self,
        bucket_name: str,
        prefix: str = "",
        *,
        max_workers: int = DEFAULT_SO_WORKERS,
        on_begin: Callable[[int], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
    ) -> int:
        items = await self.list_all_objects(bucket_name, prefix=prefix, recursive=True)
        if on_begin is not None:
            on_begin(len(items))
        keys = [item["key"] for item in items]

        async def do_delete(key: str) -> None:
            await self.delete(bucket_name, key)
            if on_delete is not None:
                on_delete(key)

        await _run_parallel_async(keys, do_delete, max_workers=max_workers)
        return len(keys)

    async def sync(
        self,
        source: str | Path,
        destination: str | Path,
        *,
        delete: bool = False,
        skip: bool = False,
        max_workers: int = DEFAULT_SO_WORKERS,
        on_transfer: Callable[[str], None] | None = None,
        on_skip: Callable[[str], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
        on_begin: Callable[[int], None] | None = None,
        on_transfer_begin: Callable[[int, int], None] | None = None,
        on_bytes: Callable[[int], None] | None = None,
        on_file_begin: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, int]:
        """Sync ``source`` → ``destination`` (local↔bucket or bucket↔bucket)."""
        src = str(source)
        dst = str(destination)
        src_remote = is_so_uri(src)
        dst_remote = is_so_uri(dst)

        common: dict[str, Any] = {
            "delete": delete,
            "skip": skip,
            "max_workers": max_workers,
            "on_skip": on_skip,
            "on_delete": on_delete,
            "on_begin": on_begin,
            "on_transfer_begin": on_transfer_begin,
            "on_bytes": on_bytes,
            "on_file_begin": on_file_begin,
            "on_status": on_status,
        }

        if src_remote and dst_remote:
            src_bucket, src_prefix = parse_so_uri(src)
            dst_bucket, dst_prefix = parse_so_uri(dst)
            return await self._sync_bucket_to_bucket(
                src_bucket,
                dst_bucket,
                source_prefix=src_prefix,
                destination_prefix=dst_prefix,
                on_copy=on_transfer,
                **common,
            )
        if src_remote and not dst_remote:
            bucket_name, prefix = parse_so_uri(src)
            return await self._sync_bucket_to_local(
                bucket_name,
                dst,
                prefix=prefix,
                on_download=on_transfer,
                **common,
            )
        if not src_remote and dst_remote:
            bucket_name, prefix = parse_so_uri(dst)
            return await self._sync_local_to_bucket(
                src,
                bucket_name,
                prefix=prefix,
                on_upload=on_transfer,
                **common,
            )
        raise HomeCloudError(
            "One or both sides must be an so:// URI. "
            "Examples: ./dir so://bucket/  |  so://bucket/ ./dir  |  so://a/ so://b/"
        )

    async def sync_local_to_bucket(
        self,
        local_dir: str | Path,
        bucket_name: str,
        *,
        prefix: str = "",
        delete: bool = False,
        skip: bool = False,
        max_workers: int = DEFAULT_SO_WORKERS,
        on_upload: Callable[[str], None] | None = None,
        on_skip: Callable[[str], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
        on_begin: Callable[[int], None] | None = None,
        on_transfer_begin: Callable[[int, int], None] | None = None,
        on_bytes: Callable[[int], None] | None = None,
        on_file_begin: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, int]:
        """Prefer :meth:`sync` with ``sync("./dir", "so://bucket/prefix")``."""
        return await self._sync_local_to_bucket(
            local_dir,
            bucket_name,
            prefix=prefix,
            delete=delete,
            skip=skip,
            max_workers=max_workers,
            on_upload=on_upload,
            on_skip=on_skip,
            on_delete=on_delete,
            on_begin=on_begin,
            on_transfer_begin=on_transfer_begin,
            on_bytes=on_bytes,
            on_file_begin=on_file_begin,
            on_status=on_status,
        )

    async def sync_bucket_to_local(
        self,
        bucket_name: str,
        local_dir: str | Path,
        *,
        prefix: str = "",
        delete: bool = False,
        skip: bool = False,
        max_workers: int = DEFAULT_SO_WORKERS,
        on_download: Callable[[str], None] | None = None,
        on_skip: Callable[[str], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
        on_begin: Callable[[int], None] | None = None,
        on_transfer_begin: Callable[[int, int], None] | None = None,
        on_bytes: Callable[[int], None] | None = None,
        on_file_begin: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, int]:
        """Prefer :meth:`sync` with ``sync("so://bucket/prefix", "./dir")``."""
        return await self._sync_bucket_to_local(
            bucket_name,
            local_dir,
            prefix=prefix,
            delete=delete,
            skip=skip,
            max_workers=max_workers,
            on_download=on_download,
            on_skip=on_skip,
            on_delete=on_delete,
            on_begin=on_begin,
            on_transfer_begin=on_transfer_begin,
            on_bytes=on_bytes,
            on_file_begin=on_file_begin,
            on_status=on_status,
        )

    async def _sync_local_to_bucket(
        self,
        local_dir: str | Path,
        bucket_name: str,
        *,
        prefix: str = "",
        delete: bool = False,
        skip: bool = False,
        max_workers: int = DEFAULT_SO_WORKERS,
        on_upload: Callable[[str], None] | None = None,
        on_skip: Callable[[str], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
        on_begin: Callable[[int], None] | None = None,
        on_transfer_begin: Callable[[int, int], None] | None = None,
        on_bytes: Callable[[int], None] | None = None,
        on_file_begin: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, int]:
        root = Path(local_dir)
        if not root.is_dir():
            raise HomeCloudError(f"Not a directory: {local_dir}")

        prefix_clean = prefix.strip("/")
        local_files: dict[str, Path] = {}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            key = sync_join_prefix(prefix_clean, rel)
            local_files[key] = path

        remote_items = await self.list_all_objects(
            bucket_name,
            prefix=prefix_clean,
            recursive=True,
        )
        remote_by_key = {item["key"]: item for item in remote_items}

        to_upload: list[str] = []
        to_skip: list[str] = []
        for key, path in sorted(local_files.items()):
            remote = remote_by_key.get(key)
            local_size = path.stat().st_size
            if skip and remote is not None and remote.get("size") == local_size:
                to_skip.append(key)
            else:
                to_upload.append(key)

        to_delete = (
            [key for key in remote_by_key if key not in local_files]
            if delete
            else []
        )

        total_ops = len(to_upload) + len(to_skip) + len(to_delete)
        transfer_bytes = sum(local_files[key].stat().st_size for key in to_upload)
        if on_status is not None:
            on_status(
                f"scan  {len(local_files)} local, {len(remote_by_key)} remote, {total_ops} operations"
            )
        if on_begin is not None:
            on_begin(total_ops)
        if on_transfer_begin is not None:
            on_transfer_begin(transfer_bytes, len(to_upload))

        skipped = 0
        for key in to_skip:
            if on_skip is not None:
                on_skip(key)
            skipped += 1

        async def do_upload(key: str) -> None:
            path = local_files[key]
            if on_file_begin is not None:
                on_file_begin(key)
            await self.upload(bucket_name, path.as_posix(), key=key, on_bytes=on_bytes)
            if on_upload is not None:
                on_upload(key)

        await _run_parallel_async(to_upload, do_upload, max_workers=max_workers)
        uploaded = len(to_upload)

        async def do_delete(key: str) -> None:
            await self.delete(bucket_name, key)
            if on_delete is not None:
                on_delete(key)

        await _run_parallel_async(to_delete, do_delete, max_workers=max_workers)
        deleted = len(to_delete)

        return {"uploaded": uploaded, "skipped": skipped, "deleted": deleted}

    async def _sync_bucket_to_local(
        self,
        bucket_name: str,
        local_dir: str | Path,
        *,
        prefix: str = "",
        delete: bool = False,
        skip: bool = False,
        max_workers: int = DEFAULT_SO_WORKERS,
        on_download: Callable[[str], None] | None = None,
        on_skip: Callable[[str], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
        on_begin: Callable[[int], None] | None = None,
        on_transfer_begin: Callable[[int, int], None] | None = None,
        on_bytes: Callable[[int], None] | None = None,
        on_file_begin: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, int]:
        root = Path(local_dir)
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise HomeCloudError(f"Not a directory: {local_dir}")

        prefix_clean = prefix.strip("/")
        remote_by_key = await self._remote_objects_for_sync(bucket_name, prefix_clean)

        local_files: dict[str, Path] = {}
        if root.exists():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(root).as_posix()
                key = sync_join_prefix(prefix_clean, rel)
                local_files[key] = path

        to_download: list[str] = []
        to_skip: list[str] = []
        for key in sorted(remote_by_key):
            remote = remote_by_key[key]
            local_path = local_files.get(key)
            remote_size = int(remote.get("size") or 0)
            if (
                skip
                and local_path is not None
                and local_path.is_file()
                and local_path.stat().st_size == remote_size
            ):
                to_skip.append(key)
            else:
                to_download.append(key)

        to_delete = (
            [key for key in local_files if key not in remote_by_key]
            if delete
            else []
        )

        total_ops = len(to_download) + len(to_skip) + len(to_delete)
        transfer_bytes = sum(int(remote_by_key[key].get("size") or 0) for key in to_download)
        if on_status is not None:
            on_status(
                f"scan  {len(remote_by_key)} remote, {len(local_files)} local, {total_ops} operations"
            )
        if on_begin is not None:
            on_begin(total_ops)
        if on_transfer_begin is not None:
            on_transfer_begin(transfer_bytes, len(to_download))

        skipped = 0
        for key in to_skip:
            if on_skip is not None:
                on_skip(key)
            skipped += 1

        async def do_download(key: str) -> None:
            rel = sync_relative_local_path(key, prefix_clean)
            dest = root / rel
            if on_file_begin is not None:
                on_file_begin(key)
            await self.download(bucket_name, key, dest_path=dest, on_bytes=on_bytes)
            local_files[key] = dest
            if on_download is not None:
                on_download(key)

        await _run_parallel_async(to_download, do_download, max_workers=max_workers)
        downloaded = len(to_download)

        deleted = 0
        for key in to_delete:
            path = local_files[key]
            if path.is_file():
                path.unlink()
            if on_delete is not None:
                on_delete(key)
            deleted += 1

        return {"downloaded": downloaded, "skipped": skipped, "deleted": deleted}

    async def _sync_bucket_to_bucket(
        self,
        source_bucket: str,
        destination_bucket: str,
        *,
        source_prefix: str = "",
        destination_prefix: str = "",
        delete: bool = False,
        skip: bool = False,
        max_workers: int = DEFAULT_SO_WORKERS,
        on_copy: Callable[[str], None] | None = None,
        on_skip: Callable[[str], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
        on_begin: Callable[[int], None] | None = None,
        on_transfer_begin: Callable[[int, int], None] | None = None,
        on_bytes: Callable[[int], None] | None = None,
        on_file_begin: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> dict[str, int]:
        src_prefix = source_prefix.strip("/")
        dst_prefix = destination_prefix.strip("/")

        if source_bucket == destination_bucket and src_prefix == dst_prefix:
            raise HomeCloudError(
                f"Source and destination are the same: {format_so_uri(source_bucket, src_prefix)}"
            )

        source_by_key = await self._remote_objects_for_sync(source_bucket, src_prefix)
        dest_by_key = await self._remote_objects_for_sync(destination_bucket, dst_prefix)

        source_rels: dict[str, tuple[str, int]] = {}
        for key, item in source_by_key.items():
            rel = sync_relative_local_path(key, src_prefix)
            source_rels[rel] = (key, int(item.get("size") or 0))

        dest_rels: dict[str, tuple[str, int]] = {}
        for key, item in dest_by_key.items():
            rel = sync_relative_local_path(key, dst_prefix)
            dest_rels[rel] = (key, int(item.get("size") or 0))

        to_copy: list[str] = []
        to_skip: list[str] = []
        for rel in sorted(source_rels):
            src_key, src_size = source_rels[rel]
            dest_entry = dest_rels.get(rel)
            if skip and dest_entry is not None and dest_entry[1] == src_size:
                to_skip.append(rel)
            else:
                to_copy.append(rel)

        to_delete_rels = (
            [rel for rel in dest_rels if rel not in source_rels] if delete else []
        )

        total_ops = len(to_copy) + len(to_skip) + len(to_delete_rels)
        transfer_bytes = sum(source_rels[rel][1] for rel in to_copy)
        if on_status is not None:
            on_status(
                f"scan  {len(source_rels)} source, {len(dest_rels)} dest, {total_ops} operations"
            )
        if on_begin is not None:
            on_begin(total_ops)
        if on_transfer_begin is not None:
            on_transfer_begin(transfer_bytes, len(to_copy))

        skipped = 0
        for rel in to_skip:
            src_key, _ = source_rels[rel]
            if on_skip is not None:
                on_skip(src_key)
            skipped += 1

        cross_bucket = source_bucket != destination_bucket

        async def do_copy(rel: str) -> None:
            src_key, size = source_rels[rel]
            dst_key = sync_join_prefix(dst_prefix, rel)
            if on_file_begin is not None:
                on_file_begin(src_key)
            await self.copy(
                destination_bucket,
                src_key,
                dst_key,
                source_bucket=source_bucket if cross_bucket else None,
            )
            if on_bytes is not None:
                on_bytes(size)
            if on_copy is not None:
                on_copy(src_key)

        await _run_parallel_async(to_copy, do_copy, max_workers=max_workers)
        copied = len(to_copy)

        async def do_delete(rel: str) -> None:
            dst_key, _ = dest_rels[rel]
            await self.delete(destination_bucket, dst_key)
            if on_delete is not None:
                on_delete(dst_key)

        await _run_parallel_async(to_delete_rels, do_delete, max_workers=max_workers)
        deleted = len(to_delete_rels)

        return {"copied": copied, "skipped": skipped, "deleted": deleted}


AsyncStorageAPI = AsyncSoAPI


class AsyncSecretsAPI:
    def __init__(self, ctx: AsyncCoreContext) -> None:
        self._ctx = ctx

    async def list(self) -> list[dict[str, Any]]:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        data = await self._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/secrets"
        )
        return data.get("items", [])


class AsyncMailAPI:
    def __init__(self, ctx: AsyncCoreContext) -> None:
        self._ctx = ctx

    async def list_mailboxes(self) -> list[dict[str, Any]]:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        data = await self._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/mail/mailboxes"
        )
        return data.get("items", [])

    async def list_messages(
        self,
        *,
        mailbox_id: str | None = None,
        folder: str | None = None,
        direction: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        params: dict[str, Any] = {"limit": limit}
        if mailbox_id:
            params["mailbox_id"] = mailbox_id
        if folder:
            params["folder"] = folder
        if direction:
            params["direction"] = direction
        if status:
            params["status"] = status
        if search:
            params["search"] = search
        if cursor:
            params["cursor"] = cursor
        return await self._ctx.transport.console_request(
            "GET",
            f"accounts/{account_id}/mail/messages",
            params=params,
        )

    async def get_message(self, message_id: str) -> dict[str, Any]:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        return await self._ctx.transport.console_request(
            "GET",
            f"accounts/{account_id}/mail/messages/{message_id}",
        )

    async def download_attachment(self, message_id: str, part_id: str) -> bytes:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        return await self._ctx.transport.console_request_bytes(
            "GET",
            f"accounts/{account_id}/mail/messages/{message_id}/attachments/{part_id}",
        )


class AsyncFunctionsAPI:
    def __init__(self, ctx: AsyncCoreContext) -> None:
        self._ctx = ctx

    async def list(self) -> list[dict[str, Any]]:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        data = await self._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/functions"
        )
        return data.get("items", [])

    async def url(self, name: str) -> dict[str, Any]:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        return await self._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/functions/{name}/url"
        )

    async def invoke(self, name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._ctx.require_access_key()
        account_id = await self._ctx.account_id()
        return await self._ctx.transport.function_url_request(
            name, account_id, json=payload or {}
        )

    async def logs(self, name: str) -> list[dict[str, Any]]:
        self._ctx.require_console_session()
        account_id = await self._ctx.account_id()
        data = await self._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/functions/{name}/invocations"
        )
        return data.get("items", [])
