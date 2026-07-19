"""HomeCloud Python SDK — preferred import path.

Install: ``pip install homecloud-sdk``

```python
from homecloud import HomeCloud, AsyncHomeCloud
```

``homecloud_sdk`` remains supported for compatibility.
"""

from homecloud_sdk import (
    DEFAULT_SO_WORKERS,
    AsyncHomeCloud,
    AsyncHomeCloudClient,
    HomeCloud,
    HomeCloudClient,
    HomeCloudError,
    NotConfiguredError,
    NotLoggedInError,
    PreferBrowserLogin,
    __version__,
)

__all__ = [
    "DEFAULT_SO_WORKERS",
    "AsyncHomeCloud",
    "AsyncHomeCloudClient",
    "HomeCloud",
    "HomeCloudClient",
    "HomeCloudError",
    "NotConfiguredError",
    "NotLoggedInError",
    "PreferBrowserLogin",
    "__version__",
]
