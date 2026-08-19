# Python ↔ Node ↔ Go SDK parity

**Product expectation:** Python (`homecloud-sdk`), Node (`@homecloud-platform/sdk`), and Go (`github.com/HomeCloudLab/homecloud-sdk/go`) support the **same HomeCloud capabilities** for the same auth model and planes. Python and Node ship on tag `v*`. Go also needs **`go/v*`** (subdirectory module).

**Normative (ADR-051):**

- Public Go API **may** differ structurally from Python/Node where required for idiomatic Go.
- Observable HomeCloud behavior **must** remain equivalent unless a difference is documented as a correctness or safety fix.
- Parity does **not** require preserving unsafe or unintended behavior.

## Status

| Area | Python | Node | Go |
|------|--------|------|-----|
| Auth factories + login / loginBrowser | yes | yes | yes (`FromEnv`, `FromSTS`, …) |
| Typed HTTP errors | yes | yes | yes (`errors.As`) |
| SO data plane + console buckets + sync | yes | yes | yes (typed structs; no `Storage` alias) |
| MQ send/receive/delete/purge/DLQ (+ batch 1–10) | yes | yes | yes |
| Secrets list + get | list only / get in Node | yes | yes |
| Mail list/get/attachments | yes | yes | yes |
| Functions / Apps / Accounts / Queues | yes | yes | yes |
| IR / usage / billing / monitoring | yes | no | yes |
| Async client | `AsyncHomeCloud` | alias | `context.Context` on every call |

## Documented Go safety differences

| Behavior | Python / Node | Go |
|----------|---------------|-----|
| Retry 502/503/504 on `MQ.Send` / purge | yes | **no** (duplicate messages) |
| Retry SO upload (same object key) | yes | yes |
| Management create `Idempotency-Key` | not sent | **sent** (API already supports it) |
| Public returns | `dict` | structs (`Bucket`, `ObjectHead`, `Message`, …) |
| `client.storage` alias | yes (prefer `so`) | **omitted** — use `client.SO` |

## Auth & client construction

| Capability | Python | Node | Go |
|------------|--------|------|-----|
| Access Key constructor | yes | yes | `New` / `FromCredentials` |
| env + credentials file | `from_env` | `fromEnv` | `FromEnv` |
| `from_sts` + mailapi rewrite | yes | yes | `FromSTS` |
| `from_function_context` | yes | yes | `FromFunctionContext` |
| Console login | yes | yes | `Login` / `LoginBrowser` |

Shared contract fixtures: [`testdata/contracts/`](../testdata/contracts/).
