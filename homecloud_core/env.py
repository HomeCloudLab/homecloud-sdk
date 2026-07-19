"""Environment variable helpers — HOMECLOUD_* canonical, HC_* short aliases."""

from __future__ import annotations

import os


def env_first(*names: str) -> str | None:
    """Return the first non-empty env value among ``names`` (in order)."""
    for name in names:
        value = os.environ.get(name)
        if value is not None and value.strip() != "":
            return value
    return None


def env_profile() -> str | None:
    return env_first("HOMECLOUD_PROFILE", "HC_PROFILE")


def env_apex() -> str | None:
    value = env_first("HOMECLOUD_APEX", "HC_APEX")
    if value is None:
        return None
    return value.strip().rstrip("/")


def env_account_id() -> str | None:
    return env_first("HOMECLOUD_ACCOUNT_ID", "HC_ACCOUNT_ID")


def env_access_key_id() -> str | None:
    return env_first("HOMECLOUD_ACCESS_KEY_ID", "HC_ACCESS_KEY_ID")


def env_secret_access_key() -> str | None:
    return env_first("HOMECLOUD_SECRET_ACCESS_KEY", "HC_SECRET_ACCESS_KEY")


def env_config_dir() -> str | None:
    return env_first("HOMECLOUD_CONFIG_DIR", "HC_CONFIG_DIR")


def env_credentials_file() -> str | None:
    return env_first("HOMECLOUD_CREDENTIALS_FILE", "HC_CREDENTIALS_FILE")


def env_session_file() -> str | None:
    return env_first("HOMECLOUD_SESSION_FILE", "HC_SESSION_FILE")
