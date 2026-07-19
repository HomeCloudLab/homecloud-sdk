"""HomeCloud Python SDK — preferred import path.

Install: ``pip install homecloud-sdk``

```python
from homecloud import HomeCloud, AsyncHomeCloud, NotFoundError
```

``homecloud_sdk`` remains supported for compatibility.
"""

from homecloud_sdk import (
    DEFAULT_SO_WORKERS,
    ApiError,
    AsyncHomeCloud,
    AsyncHomeCloudClient,
    BadRequestError,
    ConflictError,
    HomeCloud,
    HomeCloudClient,
    HomeCloudError,
    NotConfiguredError,
    NotFoundError,
    NotLoggedInError,
    PermissionDeniedError,
    PreferBrowserLogin,
    RateLimitError,
    ServiceUnavailableError,
    UnauthorizedError,
    __version__,
)

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
