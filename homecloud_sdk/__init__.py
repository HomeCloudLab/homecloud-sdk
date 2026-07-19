"""Public HomeCloud Python SDK."""

from importlib.metadata import PackageNotFoundError, version

from homecloud_core.errors import (
    ApiError,
    BadRequestError,
    ConflictError,
    HomeCloudError,
    NotConfiguredError,
    NotFoundError,
    NotLoggedInError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    UnauthorizedError,
)
from homecloud_core.mfa import PreferBrowserLogin
from homecloud_sdk.async_client import AsyncHomeCloud, AsyncHomeCloudClient
from homecloud_sdk.client import HomeCloud, HomeCloudClient
from homecloud_sdk.so_parallel import DEFAULT_SO_WORKERS

try:
    __version__ = version("homecloud-sdk")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = [
    "DEFAULT_SO_WORKERS",
    "ApiError",
    "AsyncHomeCloud",
    "AsyncHomeCloudClient",
    "BadRequestError",
    "ConflictError",
    "HomeCloud",
    "HomeCloudClient",
    "HomeCloudError",
    "NotConfiguredError",
    "NotFoundError",
    "NotLoggedInError",
    "PermissionDeniedError",
    "PreferBrowserLogin",
    "RateLimitError",
    "ServiceUnavailableError",
    "UnauthorizedError",
    "__version__",
]
