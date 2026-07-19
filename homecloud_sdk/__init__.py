"""Public HomeCloud Python SDK."""

from importlib.metadata import PackageNotFoundError, version

from homecloud_core.errors import HomeCloudError, NotConfiguredError, NotLoggedInError
from homecloud_core.mfa import PreferBrowserLogin
from homecloud_sdk.client import HomeCloud, HomeCloudClient
from homecloud_sdk.so_parallel import DEFAULT_SO_WORKERS

try:
    __version__ = version("homecloud-sdk")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = [
    "DEFAULT_SO_WORKERS",
    "HomeCloud",
    "HomeCloudClient",
    "HomeCloudError",
    "NotConfiguredError",
    "NotLoggedInError",
    "PreferBrowserLogin",
    "__version__",
]
