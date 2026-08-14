"""SO object path helpers — canonical sign path vs URL-encoded request path."""

from __future__ import annotations

from urllib.parse import quote


def encode_object_key_path(key: str) -> str:
    """Encode each object key segment for the HTTP path (spaces → %20, etc.)."""
    return "/".join(quote(part, safe="") for part in key.lstrip("/").split("/"))


def so_object_paths(account_id: str, bucket_name: str, object_key: str) -> tuple[str, str]:
    """Return (sign_path, url_path) for object GET/DELETE."""
    key = object_key.lstrip("/")
    sign_path = f"/{account_id}/{bucket_name}/objects/{key}"
    url_path = f"/{account_id}/{bucket_name}/objects/{encode_object_key_path(key)}"
    return sign_path, url_path


def is_so_uri(target: str) -> bool:
    """True when ``target`` is an ``so://`` or ``s3://`` object-storage URI."""
    lowered = str(target).lower()
    return lowered.startswith("so://") or lowered.startswith("s3://")


def parse_so_uri(target: str) -> tuple[str, str]:
    """Return ``(bucket, key_or_prefix)`` from ``so://bucket/path`` (or ``s3://``).

    Raises ``ValueError`` when the URI has no bucket name.
    """
    text = str(target).strip()
    lowered = text.lower()
    if lowered.startswith("so://"):
        cleaned = text[5:]
    elif lowered.startswith("s3://"):
        cleaned = text[5:]
    else:
        cleaned = text
    cleaned = cleaned.strip("/")
    if not cleaned:
        raise ValueError("URI must include a bucket name")
    parts = cleaned.split("/", 1)
    bucket_name = parts[0]
    key_prefix = parts[1] if len(parts) > 1 else ""
    return bucket_name, key_prefix


def format_so_uri(bucket: str, key: str = "") -> str:
    """Build ``so://bucket/`` or ``so://bucket/key``."""
    if key:
        return f"so://{bucket}/{key.lstrip('/')}"
    return f"so://{bucket}/"


def sync_join_prefix(prefix_clean: str, relative: str) -> str:
    """Join a cleaned prefix with a relative object path."""
    rel = relative.lstrip("/")
    if not prefix_clean:
        return rel
    if not rel:
        return prefix_clean
    return f"{prefix_clean}/{rel}"


def sync_relative_local_path(key: str, prefix_clean: str) -> str:
    """Map remote object key to a relative path under the sync destination directory."""
    if not prefix_clean:
        return key
    if key == prefix_clean:
        return key.rsplit("/", 1)[-1]
    if key.startswith(f"{prefix_clean}/"):
        return key[len(prefix_clean) + 1 :]
    return key
