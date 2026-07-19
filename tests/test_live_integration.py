"""Live integration tests against ~/.homecloud credentials (real platform).

Uses Access Key data-plane by default (works without console JWT).
Console-only checks are skipped when the saved session token is invalid.

Optional: set HC_TEST_BUCKET / HOMECLOUD_TEST_BUCKET to pin a bucket.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import pytest

from homecloud_core.config import credentials_path, load_credentials
from homecloud_core.env import env_first
from homecloud_sdk import HomeCloudClient, HomeCloudError, NotLoggedInError


def _credentials_available() -> bool:
    try:
        path = credentials_path()
        if not path.exists():
            return False
        creds = load_credentials()
        profile = creds.get_profile(creds.default_profile)
        return bool(profile.access_key_id and profile.secret_access_key)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _credentials_available(),
    reason="No ~/.homecloud/credentials with access keys",
)

_PROBE_BUCKETS = (
    "docs",
    "ilg",
    "shapira",
    "media",
    "data",
    "backup",
    "uploads",
    "files",
    "test",
)


def _resolve_bucket(client: HomeCloudClient) -> str:
    pinned = env_first("HOMECLOUD_TEST_BUCKET", "HC_TEST_BUCKET")
    if pinned:
        return pinned.strip()

    try:
        buckets = client.so.list_buckets()
        if buckets:
            return str(buckets[0].get("name") or buckets[0].get("id"))
    except HomeCloudError:
        pass

    for name in _PROBE_BUCKETS:
        try:
            client.so.list_objects(name, page_size=1)
            return name
        except HomeCloudError as exc:
            if exc.status_code in {404, 403}:
                continue
            # Unexpected — try next candidate
            continue

    pytest.skip(
        "No usable SO bucket. Set HC_TEST_BUCKET, or create a bucket and re-login "
        "for console list_buckets."
    )


@pytest.fixture
def client() -> HomeCloudClient:
    with HomeCloudClient(interactive_mfa=False) as c:
        yield c


def test_live_config_and_whoami(client: HomeCloudClient) -> None:
    summary = client.config_summary()
    assert summary["configured"] is True
    assert summary["access_key_id"]
    account_id = client.account_id()
    assert account_id
    assert len(account_id) > 8


def test_live_list_buckets_console_optional(client: HomeCloudClient) -> None:
    try:
        buckets = client.so.list_buckets()
    except (HomeCloudError, NotLoggedInError) as exc:
        status = getattr(exc, "status_code", None)
        if status in {401, 403} or isinstance(exc, NotLoggedInError):
            pytest.skip(f"Console JWT required for list_buckets: {exc}")
        raise
    assert isinstance(buckets, list)


def test_live_so_upload_download_delete(client: HomeCloudClient, tmp_path: Path) -> None:
    bucket = _resolve_bucket(client)
    key = f"sdk-live/{uuid.uuid4().hex}.txt"
    payload = f"homecloud-sdk live test {time.time()}\n".encode()
    src = tmp_path / "upload.txt"
    src.write_bytes(payload)

    uploaded = client.so.upload(bucket, str(src), key=key)
    assert isinstance(uploaded, dict)

    dest = tmp_path / "download.txt"
    meta = client.so.download(bucket, key, dest_path=dest)
    assert dest.read_bytes() == payload
    assert meta["size"] == len(payload)

    listed = client.so.list_objects(bucket, prefix="sdk-live/", recursive=True)
    keys = {item.get("key") for item in listed.get("items", [])}
    assert key in keys

    obj_meta = client.so.head_object(bucket, key)
    assert int(obj_meta.get("size") or 0) == len(payload)
    assert obj_meta.get("key") == key
    assert "metadata" in obj_meta
    assert "tags" in obj_meta
    # Must not include object body
    assert "body" not in obj_meta
    assert "content" not in obj_meta
    assert obj_meta.get("path") is None or "path" not in obj_meta

    client.so.delete(bucket, key)
    after = client.so.list_objects(bucket, prefix=key, recursive=True)
    after_keys = {
        item.get("key") for item in after.get("items", []) if not item.get("is_dir")
    }
    assert key not in after_keys


def test_live_so_sync_roundtrip(client: HomeCloudClient, tmp_path: Path) -> None:
    bucket = _resolve_bucket(client)
    prefix = f"sdk-live-sync/{uuid.uuid4().hex}"
    local_up = tmp_path / "up"
    local_up.mkdir()
    (local_up / "a.txt").write_text("alpha\n", encoding="utf-8")
    (local_up / "nested").mkdir()
    (local_up / "nested" / "b.txt").write_text("beta\n", encoding="utf-8")

    result = client.so.sync_local_to_bucket(local_up, bucket, prefix=prefix, max_workers=2)
    assert result["uploaded"] == 2

    local_down = tmp_path / "down"
    down = client.so.sync_bucket_to_local(bucket, local_down, prefix=prefix, max_workers=2)
    assert down["downloaded"] == 2
    assert (local_down / "a.txt").read_text(encoding="utf-8") == "alpha\n"
    assert (local_down / "nested" / "b.txt").read_text(encoding="utf-8") == "beta\n"

    deleted = client.so.delete_recursive(bucket, prefix=prefix, max_workers=2)
    assert deleted == 2


def test_live_mq_optional(client: HomeCloudClient) -> None:
    try:
        queues = client.queues.list()
    except (HomeCloudError, NotLoggedInError) as exc:
        status = getattr(exc, "status_code", None)
        if status in {401, 403} or isinstance(exc, NotLoggedInError):
            pytest.skip(f"Console session required for queues.list: {exc}")
        raise

    if not queues:
        pytest.skip("No queues — skipping MQ live test")

    name = str(queues[0].get("name") or queues[0].get("slug"))
    body = {"sdk_live": True, "ts": time.time(), "id": uuid.uuid4().hex}
    try:
        sent = client.mq.send(name, body)
    except HomeCloudError as exc:
        if exc.status_code in {404, 403}:
            pytest.skip(f"Queue not available on data plane: {name} ({exc})")
        raise
    assert sent.get("message_id") or sent

    items = client.mq.receive(name, max_messages=1, wait_seconds=2)
    assert isinstance(items, list)
