# HomeCloud SDK

Polyglot SDK for HomeCloud — **Python** at the repo root (`pip install homecloud-sdk`), **Node.js** under [`js/`](./js/) (`@homecloud-platform/sdk`).

**Parity goal:** both languages expose the same HomeCloud capabilities and ship on the same `v*` tag. Track gaps in [`js/PARITY.md`](./js/PARITY.md). Node is MVP today (STS / Functions-first); full surface is the committed target.

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
client.mq.send("orders", [{"id": 1}, {"id": 2}])  # batch (1–10)

# Interactive helpers only (CLI/tools) — may involve MFA
# client.login("alice", "…")
# client.login_browser()
```

### Node.js (`@homecloud-platform/sdk`)

```js
const { HomeCloud } = require("@homecloud-platform/sdk");

const client = HomeCloud.fromSts(context.sts.archive, {
  accountId: context.account_id,
});
await client.so.putJson("docs", "a.json", { ok: true });
```

See [`js/README.md`](./js/README.md). Same STS / `mailapi` rewrite rules as Python ≥0.4.9.

Publish Node via the **same** tag as Python: `v0.5.0` runs PyPI + npm together.
See [`js/README.md`](./js/README.md) and `./scripts/bump-version.sh`.

### Async

```python
from homecloud import AsyncHomeCloud

async with AsyncHomeCloud.from_env() as client:
    meta = await client.so.head_object("docs", "a.txt")
    await client.mq.send("orders", {"id": 1})
    await client.mq.receive("orders", max_messages=10, delete=True)
```

`from homecloud_sdk import …` still works (compatibility). Prefer `from homecloud import …`.

### Errors

HTTP failures raise typed subclasses of `HomeCloudError` (catch specific types or the base):

| Type | Typical status |
|------|----------------|
| `NotFoundError` | 404 (bucket / object / queue) |
| `UnauthorizedError` | 401 |
| `PermissionDeniedError` | 403 |
| `BadRequestError` | 400 |
| `ConflictError` | 409 |
| `RateLimitError` | 429 |
| `ServiceUnavailableError` | 502–504 |
| `ApiError` | other HTTP errors |

```python
from homecloud import HomeCloud, NotFoundError, HomeCloudError

client = HomeCloud()
try:
    client.so.head_object("docs", "a.txt")
except NotFoundError as exc:
    print(exc.resource_type, exc.resource, exc)  # object / docs/a.txt / …
except HomeCloudError as exc:
    print(exc.status_code, exc)
```

## Architecture

```text
homecloud/          ← preferred public import (Python)
homecloud_core/     ← auth, routing, signing, sessions, MFA helpers
homecloud_sdk/      ← HomeCloud + AsyncHomeCloud
js/                 ← @homecloud-platform/sdk (Node.js 20+)
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
npm publish is wired via `.github/workflows/publish-npm.yml` (**same** `v*` tag → aligned versions).

```bash
./scripts/bump-version.sh 0.5.0
# commit, push, then:
git tag v0.5.0 && git push origin v0.5.0
```

## Operations by plane

| API | Auth | Notes |
|-----|------|-------|
| `so.upload` / `download` / `sync_*` / `list_objects` / `delete` | Access Key | Primary SDK path |
| `so.head_object` (`object_metadata`) | Access Key | Metadata only — no object body (AWS HeadObject) |
| `so.get_object_uri` | Access Key | `so://` + public HTTPS URL |
| `so.generate_presigned_url` | Access Key | Time-limited GET URL |
| `mq.send` / `receive` / `delete` / `purge` / DLQ | Access Key | `receive(delete=True)` fast ack; batch send via list |
| `queues.list` / `queues.get` | Console JWT | `list(live=True)` for depth/inflight/DLQ |
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

cd js && npm test
```

### Service-account verification (pre-PyPI)

Mints a dedicated Access Key named `homecloud-sdk-test` (requires a one-time
`homecloud login` to create the key), then runs a **clean subprocess** with
`HomeCloud.from_env()` — no JWT session, no MFA, no browser:

```bash
python scripts/verify_service_account_flow.py
```

Expected: `PASS: service-account flow works without login/JWT/MFA/browser`.
