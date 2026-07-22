"""Platform endpoint defaults — hidden from end users."""

from __future__ import annotations

from homecloud_core.env import env_apex

DEFAULT_APEX = "holab.abrdns.com"
DEFAULT_PROFILE = "default"
WHOAMI_PATH = "/access-key/whoami"
WHOAMI_ACCOUNT_SENTINEL = "-"


def platform_apex() -> str:
    return env_apex() or DEFAULT_APEX


def console_url(apex: str | None = None) -> str:
    host = apex or platform_apex()
    return f"https://console.{host}/api/v1"


def console_web_url(apex: str | None = None) -> str:
    host = apex or platform_apex()
    return f"https://console.{host}"


def mq_url(apex: str | None = None) -> str:
    host = apex or platform_apex()
    return f"https://mq.{host}"


def so_url(apex: str | None = None) -> str:
    host = apex or platform_apex()
    return f"https://so.{host}"


def secrets_url(apex: str | None = None) -> str:
    host = apex or platform_apex()
    return f"https://secrets.{host}"


def mail_api_url(apex: str | None = None) -> str:
    """Mail data-plane SigV1 host (not SMTP mail.{domain})."""
    host = apex or platform_apex()
    return f"https://mailapi.{host}"


def function_url(name: str, apex: str | None = None) -> str:
    """Data-plane Function URL: https://{name}.func.{apex}."""
    host = apex or platform_apex()
    return f"https://{name.strip().lower()}.func.{host}"
