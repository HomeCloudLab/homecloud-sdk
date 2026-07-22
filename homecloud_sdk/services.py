"""Service APIs — thin facades over CoreContext."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from homecloud_core.context import CoreContext
from homecloud_core.errors import HomeCloudError
from homecloud_core.progress_reader import ProgressReader
from homecloud_core.so_paths import so_object_paths, sync_relative_local_path
from homecloud_sdk.so_parallel import DEFAULT_SO_WORKERS, run_parallel


class AccountsAPI:
    def __init__(self, ctx: CoreContext) -> None:
        self._ctx = ctx

    def list(self) -> list[dict[str, Any]]:
        """Console JWT — interactive / CLI management."""
        return self._ctx.list_accounts()

    def switch(self, account_ref: str) -> None:
        """Console JWT — interactive / CLI management."""
        self._ctx.switch_account(account_ref)


class QueuesAPI:
    def __init__(self, ctx: CoreContext) -> None:
        self._ctx = ctx

    def list(self) -> list[dict[str, Any]]:
        """List queue definitions via Console API (JWT). Runtime send/receive: ``client.mq``."""
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        data = self._ctx.transport.console_request("GET", f"accounts/{account_id}/queues")
        return data.get("items", [])


class MqAPI:
    def __init__(self, ctx: CoreContext) -> None:
        self._ctx = ctx

    def send(
        self,
        queue_name: str,
        body: dict[str, Any] | str,
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Data plane — Access Key only (no MFA / JWT)."""
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        path = f"/{account_id}/{queue_name}/messages"
        body_str = body if isinstance(body, str) else json.dumps(body)
        payload: dict[str, Any] = {"body": body_str}
        if headers:
            payload["headers"] = headers
        return self._ctx.transport.data_plane_request(
            "mq",
            "POST",
            path,
            account_id,
            json=payload,
        )

    def receive(
        self,
        queue_name: str,
        *,
        max_messages: int = 1,
        wait_seconds: int = 20,
    ) -> list[dict[str, Any]]:
        """Data plane — Access Key only (no MFA / JWT)."""
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        path = f"/{account_id}/{queue_name}/messages"
        data = self._ctx.transport.data_plane_request(
            "mq",
            "GET",
            path,
            account_id,
            params={"max_messages": max_messages, "wait_seconds": wait_seconds},
        )
        return data.get("items", [])


class AppsAPI:
    def __init__(self, ctx: CoreContext) -> None:
        self._ctx = ctx

    def list(self) -> list[dict[str, Any]]:
        """Console JWT — interactive / CLI management."""
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        data = self._ctx.transport.console_request("GET", f"accounts/{account_id}/applications")
        return data.get("items", [])


class SoAPI:
    """Object storage (SO) — use client.so, not client.storage."""

    def __init__(self, ctx: CoreContext) -> None:
        self._ctx = ctx

    def list_buckets(self) -> list[dict[str, Any]]:
        """Console JWT management helper. Object ops use Access Keys (no login)."""
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        try:
            data = self._ctx.transport.console_request(
                "GET", f"accounts/{account_id}/storage/buckets"
            )
        except HomeCloudError as exc:
            if exc.status_code in {401, 403}:
                raise HomeCloudError(
                    "list_buckets requires a valid console login. "
                    "Run: homecloud login. For automation, call so.list_objects(bucket) "
                    "with Access Keys (no JWT).",
                    status_code=exc.status_code,
                    detail=exc.detail,
                ) from exc
            raise
        return data.get("items", [])

    def create_bucket(self, name: str) -> dict[str, Any]:
        """Create a bucket via Console API (JWT + resources.create)."""
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        return self._ctx.transport.console_request(
            "POST",
            f"accounts/{account_id}/storage/buckets",
            json={"name": name.strip().lower()},
        )

    def delete_bucket(self, name: str) -> None:
        """Delete a bucket via Console API (JWT + resources.delete)."""
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        self._ctx.transport.console_request(
            "DELETE",
            f"accounts/{account_id}/storage/buckets/{name.strip().lower()}",
        )

    def list_objects(
        self,
        bucket_name: str,
        *,
        prefix: str = "",
        recursive: bool = False,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """Data plane — Access Key only."""
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        path = f"/{account_id}/{bucket_name}/objects"
        return self._ctx.transport.data_plane_request(
            "so",
            "GET",
            path,
            account_id,
            params={
                "prefix": prefix,
                "recursive": recursive,
                "page": page,
                "page_size": page_size,
            },
        )

    def upload(
        self,
        bucket_name: str,
        file_path: str,
        *,
        key: str | None = None,
        on_bytes: Callable[[int], None] | None = None,
    ) -> dict[str, Any]:
        """Data plane — Access Key only."""
        self._ctx.require_access_key()
        from pathlib import Path

        path = Path(file_path)
        if not path.is_file():
            raise HomeCloudError(f"File not found: {file_path}")

        object_key = key or path.name
        account_id = self._ctx.account_id()
        upload_path = f"/{account_id}/{bucket_name}/objects"
        with path.open("rb") as handle:
            body = ProgressReader(handle, on_bytes) if on_bytes is not None else handle
            return self._ctx.transport.data_plane_request(
                "so",
                "POST",
                upload_path,
                account_id,
                data={"key": object_key},
                files={"file": (path.name, body, "application/octet-stream")},
            )

    def delete(self, bucket_name: str, object_key: str) -> None:
        """Data plane — Access Key only."""
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        sign_path, url_path = so_object_paths(account_id, bucket_name, object_key)
        self._ctx.transport.data_plane_request(
            "so",
            "DELETE",
            sign_path,
            account_id,
            url_path=url_path,
        )

    def download(
        self,
        bucket_name: str,
        object_key: str,
        *,
        dest_path: str | Path,
        on_bytes: Callable[[int], None] | None = None,
    ) -> dict[str, Any]:
        """Data plane — Access Key only."""
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        key = object_key.lstrip("/")
        sign_path, url_path = so_object_paths(account_id, bucket_name, key)
        dest = Path(dest_path)
        nbytes = self._ctx.transport.data_plane_download_to_file(
            "so",
            sign_path,
            account_id,
            dest,
            url_path=url_path,
            on_chunk=on_bytes,
        )
        return {"key": key, "size": nbytes, "path": str(dest)}

    def head_object(self, bucket_name: str, object_key: str) -> dict[str, Any]:
        """Return object metadata only (no body) — Access Key data plane.

        Equivalent to AWS ``head_object`` / S3 HeadObject: size, etag,
        content_type, last_modified, user metadata, and tags — without
        downloading the object bytes.
        """
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        key = object_key.lstrip("/")
        sign_path, url_path = so_object_paths(account_id, bucket_name, key)
        raw = self._ctx.transport.data_plane_request(
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

    def object_metadata(self, bucket_name: str, object_key: str) -> dict[str, Any]:
        """Alias for :meth:`head_object` (kept for existing callers)."""
        return self.head_object(bucket_name, object_key)

    def get_object_uri(self, bucket_name: str, object_key: str) -> dict[str, Any]:
        """Return canonical object URIs (Access Key data plane).

        Response includes:
        - ``so_uri`` — ``so://bucket/key``
        - ``https_url`` — virtual-hosted HTTPS URL (requires public bucket access)
        - ``https_requires_public`` — whether HTTPS works without auth
        """
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        key = object_key.lstrip("/")
        sign_path, url_path = so_object_paths(account_id, bucket_name, key)
        raw = self._ctx.transport.data_plane_request(
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

    def generate_presigned_url(
        self,
        bucket_name: str,
        object_key: str,
        *,
        expires: int = 3600,
    ) -> dict[str, Any]:
        """Generate a time-limited GET URL for an object (Access Key data plane).

        ``expires`` is seconds (platform allows 60–604800). Returns ``url`` and
        ``expires_in_seconds``.
        """
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        key = object_key.lstrip("/")
        sign_path, url_path = so_object_paths(account_id, bucket_name, key)
        raw = self._ctx.transport.data_plane_request(
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

    def _remote_objects_for_sync(
        self,
        bucket_name: str,
        prefix_clean: str,
    ) -> dict[str, dict[str, Any]]:
        remote_items = self.list_all_objects(
            bucket_name,
            prefix=prefix_clean,
            recursive=True,
        )
        remote_by_key = {item["key"]: item for item in remote_items}
        # List API omits the object when prefix equals the exact key (folder placeholder filter).
        if not remote_by_key and prefix_clean and not prefix_clean.endswith("/"):
            try:
                meta = self.object_metadata(bucket_name, prefix_clean)
            except HomeCloudError:
                return remote_by_key
            remote_by_key[prefix_clean] = {
                "key": prefix_clean,
                "size": int(meta.get("size") or 0),
                "is_dir": False,
            }
        return remote_by_key

    def list_all_objects(
        self,
        bucket_name: str,
        *,
        prefix: str = "",
        recursive: bool = True,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.list_objects(
                bucket_name,
                prefix=prefix,
                recursive=recursive,
                page=page,
                page_size=100,
            )
            items.extend(
                item for item in data.get("items", []) if not item.get("is_dir")
            )
            if page >= int(data.get("pages", 1)):
                break
            page += 1
        return items

    def delete_recursive(
        self,
        bucket_name: str,
        prefix: str = "",
        *,
        max_workers: int = DEFAULT_SO_WORKERS,
        on_begin: Callable[[int], None] | None = None,
        on_delete: Callable[[str], None] | None = None,
    ) -> int:
        items = self.list_all_objects(bucket_name, prefix=prefix, recursive=True)
        if on_begin is not None:
            on_begin(len(items))
        keys = [item["key"] for item in items]

        def do_delete(key: str) -> None:
            self.delete(bucket_name, key)
            if on_delete is not None:
                on_delete(key)

        run_parallel(keys, do_delete, max_workers=max_workers)
        return len(keys)

    def sync_local_to_bucket(
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
        """Upload local directory to bucket (one-way). Overwrites by default; use skip=True to skip same-size keys."""
        root = Path(local_dir)
        if not root.is_dir():
            raise HomeCloudError(f"Not a directory: {local_dir}")

        prefix_clean = prefix.strip("/")
        local_files: dict[str, Path] = {}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            key = f"{prefix_clean}/{rel}" if prefix_clean else rel
            local_files[key] = path

        remote_items = self.list_all_objects(
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
            on_status(f"scan  {len(local_files)} local, {len(remote_by_key)} remote, {total_ops} operations")
        if on_begin is not None:
            on_begin(total_ops)
        if on_transfer_begin is not None:
            on_transfer_begin(transfer_bytes, len(to_upload))

        skipped = 0
        for key in to_skip:
            if on_skip is not None:
                on_skip(key)
            skipped += 1

        def do_upload(key: str) -> None:
            path = local_files[key]
            if on_file_begin is not None:
                on_file_begin(key)
            self.upload(bucket_name, path.as_posix(), key=key, on_bytes=on_bytes)
            if on_upload is not None:
                on_upload(key)

        run_parallel(to_upload, do_upload, max_workers=max_workers)
        uploaded = len(to_upload)

        deleted = 0

        def do_delete(key: str) -> None:
            self.delete(bucket_name, key)
            if on_delete is not None:
                on_delete(key)

        run_parallel(to_delete, do_delete, max_workers=max_workers)
        deleted = len(to_delete)

        return {"uploaded": uploaded, "skipped": skipped, "deleted": deleted}

    def sync_bucket_to_local(
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
        """Download bucket prefix to local directory. Overwrites by default; use skip=True to skip same-size files."""
        root = Path(local_dir)
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise HomeCloudError(f"Not a directory: {local_dir}")

        prefix_clean = prefix.strip("/")
        remote_by_key = self._remote_objects_for_sync(bucket_name, prefix_clean)

        local_files: dict[str, Path] = {}
        if root.exists():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(root).as_posix()
                key = f"{prefix_clean}/{rel}" if prefix_clean else rel
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

        def do_download(key: str) -> None:
            rel = sync_relative_local_path(key, prefix_clean)
            dest = root / rel
            if on_file_begin is not None:
                on_file_begin(key)
            self.download(bucket_name, key, dest_path=dest, on_bytes=on_bytes)
            local_files[key] = dest
            if on_download is not None:
                on_download(key)

        run_parallel(to_download, do_download, max_workers=max_workers)
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


StorageAPI = SoAPI


class SecretsAPI:
    def __init__(self, ctx: CoreContext) -> None:
        self._ctx = ctx

    def list(self) -> list[dict[str, Any]]:
        """Console JWT — secrets metadata listing (management plane)."""
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        data = self._ctx.transport.console_request("GET", f"accounts/{account_id}/secrets")
        return data.get("items", [])


class MailAPI:
    """HomeCloud Mail — JWT (interactive) or Access Key / mail STS (automation)."""

    def __init__(self, ctx: CoreContext) -> None:
        self._ctx = ctx

    def _mail_request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
        if self._ctx.has_access_key:
            return self._ctx.transport.console_signed_request(
                method,
                path,
                self._ctx.account_id(),
                params=params,
            )
        self._ctx.require_console_session()
        return self._ctx.transport.console_request(method, path, params=params)

    def _mail_request_bytes(self, method: str, path: str) -> bytes:
        if self._ctx.has_access_key:
            return self._ctx.transport.console_signed_request_bytes(
                method,
                path,
                self._ctx.account_id(),
            )
        self._ctx.require_console_session()
        return self._ctx.transport.console_request_bytes(method, path)

    def list_mailboxes(self) -> list[dict[str, Any]]:
        account_id = self._ctx.account_id()
        data = self._mail_request("GET", f"accounts/{account_id}/mail/mailboxes")
        return data.get("items", [])

    def list_messages(
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
        """List message metadata. Returns ``{items, next_cursor, has_more}``."""
        account_id = self._ctx.account_id()
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
        return self._mail_request(
            "GET",
            f"accounts/{account_id}/mail/messages",
            params=params,
        )

    def get_message(self, message_id: str) -> dict[str, Any]:
        """Full message detail including ``body_html``, ``body_text``, and ``attachments`` metadata."""
        account_id = self._ctx.account_id()
        return self._mail_request(
            "GET",
            f"accounts/{account_id}/mail/messages/{message_id}",
        )

    def download_attachment(self, message_id: str, part_id: str) -> bytes:
        """Download one MIME part (attachment) as raw bytes."""
        account_id = self._ctx.account_id()
        return self._mail_request_bytes(
            "GET",
            f"accounts/{account_id}/mail/messages/{message_id}/attachments/{part_id}",
        )


class FunctionsAPI:
    """HomeCloud Functions — management (JWT) + Function URL invoke (Access Key)."""

    def __init__(self, ctx: CoreContext) -> None:
        self._ctx = ctx

    def list(self) -> list[dict[str, Any]]:
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        data = self._ctx.transport.console_request("GET", f"accounts/{account_id}/functions")
        return data.get("items", [])

    def url(self, name: str) -> dict[str, Any]:
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        return self._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/functions/{name}/url"
        )

    def enable_url(
        self,
        name: str,
        *,
        public: bool = False,
        rate_limit_per_minute: int = 60,
    ) -> dict[str, Any]:
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        return self._ctx.transport.console_request(
            "POST",
            f"accounts/{account_id}/functions/{name}/url/enable",
            json={
                "public_url_enabled": public,
                "rate_limit_per_minute": rate_limit_per_minute,
            },
        )

    def disable_url(self, name: str) -> dict[str, Any]:
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        return self._ctx.transport.console_request(
            "POST", f"accounts/{account_id}/functions/{name}/url/disable"
        )

    def invoke(self, name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        """Data plane Function URL invoke — Access Key HMAC (not console JWT)."""
        self._ctx.require_access_key()
        account_id = self._ctx.account_id()
        return self._ctx.transport.function_url_request(
            name,
            account_id,
            json=payload or {},
        )

    def logs(self, name: str) -> list[dict[str, Any]]:
        """List recent invocations (management plane)."""
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        data = self._ctx.transport.console_request(
            "GET", f"accounts/{account_id}/functions/{name}/invocations"
        )
        return data.get("items", [])

    def get_invocation(self, name: str, invocation_id: str) -> dict[str, Any]:
        """Full invocation detail including logs (management plane)."""
        self._ctx.require_console_session()
        account_id = self._ctx.account_id()
        return self._ctx.transport.console_request(
            "GET",
            f"accounts/{account_id}/functions/{name}/invocations/{invocation_id}",
        )
