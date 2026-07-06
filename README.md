# HomeCloud SDK

Python SDK and internal core for HomeCloud. This is the **PyPI package** (`pip install homecloud-sdk`).

## Architecture

```text
homecloud_core/     ← all logic (auth, routing, signing, sessions)
homecloud_sdk/      ← public API (HomeCloudClient)
```

CLI (`homecloud-cli`) is a thin wrapper — it only calls `HomeCloudClient`.

## Usage

```python
from homecloud_sdk import HomeCloudClient

client = HomeCloudClient()

client.login("you@example.com", "password")
client.apps.list()
client.mq.send("orders", {"id": 1})
client.queues.list()
```

## Configuration

| File | Purpose |
|------|---------|
| `~/.homecloud/credentials` | Access Keys (persistent) |
| `~/.homecloud/session` | Login session (temporary) |

Users never pass account IDs, JWT, or endpoint URLs.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -q
```
