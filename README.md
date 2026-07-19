# HomeCloud SDK

Python SDK for HomeCloud (`pip install homecloud-sdk`).

## Auth model (cloud-style)

| Who | How | MFA |
|-----|-----|-----|
| **SDK / automation** | Access Key ID + Secret (SigV1 data plane) | Never on requests |
| **CLI / humans** | `homecloud login` → console JWT | At login / step-up only |

Access Keys are created once in the Console (human + MFA there). Runtime SDK calls do **not** re-prompt MFA.

```python
from homecloud import HomeCloud

# Recommended — explicit credentials (CI / servers)
client = HomeCloud(
    access_key="HCAK...",
    secret_key="...",
)

# Or environment (HOMECLOUD_* / HC_*)
client = HomeCloud.from_env()

# Or ~/.homecloud/credentials (+ optional HC_PROFILE)
client = HomeCloud()

# Data plane — Access Key only, no login
client.so.upload("docs", "./file.txt", key="a.txt")
client.mq.send("orders", {"id": 1})

# Interactive helpers only (CLI/tools) — may involve MFA
# client.login("alice", "…")
# client.login_browser()
```

### Async

```python
from homecloud import AsyncHomeCloud

async with AsyncHomeCloud.from_env() as client:
    meta = await client.so.head_object("docs", "a.txt")
    await client.mq.send("orders", {"id": 1})
```

`from homecloud_sdk import …` still works (compatibility). Prefer `from homecloud import …`.

## Architecture

```text
homecloud/          ← preferred public import
homecloud_core/     ← auth, routing, signing, sessions, MFA helpers
homecloud_sdk/      ← HomeCloud + AsyncHomeCloud
```

CLI (`homecloud-cli`) is a Typer/Rich wrapper; it opts into `interactive_mfa=True` on the sync client.

## Install

```bash
pip install homecloud-sdk
```

Until PyPI is configured, use a Git checkout or sibling editable install:

```bash
pip install -e "../homecloud-sdk"
```

PyPI publish is wired via `.github/workflows/publish-pypi.yml` (tag `v*` + Trusted Publishing).

## Operations by plane

| API | Auth | Notes |
|-----|------|-------|
| `so.upload` / `download` / `sync_*` / `list_objects` / `delete` | Access Key | Primary SDK path |
| `so.head_object` (`object_metadata`) | Access Key | Metadata only — no object body (AWS HeadObject) |
| `so.get_object_uri` | Access Key | `so://` + public HTTPS URL |
| `so.generate_presigned_url` | Access Key | Time-limited GET URL |
| `mq.send` / `receive` | Access Key | Primary SDK path |
| `account_id()` | Access Key whoami | No JWT |
| `so.list_buckets` / `create_bucket` | Console JWT | Management helper |
| `queues.list` / `apps.list` / `accounts.*` | Console JWT | Management helper |

Async mirrors the same surface on `AsyncHomeCloud` (`await client.so.…`).

## Configuration

| File | Purpose |
|------|---------|
| `~/.homecloud/credentials` | Access Keys (multi-profile JSON) |
| `~/.homecloud/session` | Console JWT (interactive only) |

### Profile / env

1. Constructor `profile=` / `access_key_id=` …
2. `HOMECLOUD_PROFILE` / `HC_PROFILE`
3. credentials `default_profile`
4. `default`

| Variable | Short | Effect |
|----------|-------|--------|
| `HOMECLOUD_PROFILE` | `HC_PROFILE` | Active profile |
| `HOMECLOUD_ACCESS_KEY_ID` | `HC_ACCESS_KEY_ID` | Access key |
| `HOMECLOUD_SECRET_ACCESS_KEY` | `HC_SECRET_ACCESS_KEY` | Secret |
| `HOMECLOUD_ACCOUNT_ID` | `HC_ACCOUNT_ID` | Optional account |
| `HOMECLOUD_APEX` | `HC_APEX` | Platform domain |

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -q
pytest tests/test_live_integration.py -q   # needs Access Keys in ~/.homecloud
```

### Service-account verification (pre-PyPI)

Mints a dedicated Access Key named `homecloud-sdk-test` (requires a one-time
`homecloud login` to create the key), then runs a **clean subprocess** with
`HomeCloud.from_env()` — no JWT session, no MFA, no browser:

```bash
python scripts/verify_service_account_flow.py
```

Expected: `PASS: service-account flow works without login/JWT/MFA/browser`.
