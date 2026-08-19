# Python ↔ Node ↔ Go ↔ Java SDK parity

**Product expectation:** Python (`homecloud-sdk`), Node (`@homecloud-platform/sdk`), Go (`github.com/HomeCloudLab/homecloud-sdk/go`), and Java (`com.homecloudlab:homecloud-sdk`) support the **same HomeCloud capabilities** for the same auth model and planes. Python, Node, and Java ship on tag `v*`. Go also needs **`go/v*`** (subdirectory module).

**Normative (ADR-051 / ADR-052):**

- Public API **may** differ structurally where the language requires it.
- Observable HomeCloud behavior **must** remain equivalent unless a difference is documented as a correctness or safety fix.
- Parity does **not** require preserving unsafe or unintended behavior.

**Patches:** A language-only patch is allowed for implementation bugs (NPE, JSON mapping, paths). A change to retry, error mapping, timeouts, SigV1, or STS rewrite must ship in **all** SDKs.

## Status

| Area | Python | Node | Go | Java |
|------|--------|------|----|------|
| Auth factories + login / loginBrowser | yes | yes | yes (`FromEnv`, `FromSTS`, …) | yes (`fromEnv`, `fromSts`, `HomeCloudAuth`) |
| Typed HTTP errors | yes | yes | yes (`errors.As`) | yes (`RuntimeException` hierarchy) |
| SO data plane + console buckets + sync | yes | yes | yes (typed structs; no `Storage` alias) | yes (records; no `storage` alias) |
| MQ send/receive/delete/purge/DLQ (+ batch 1–10) | yes | yes | yes | yes |
| Secrets list + get | list only / get in Node | yes | yes | yes |
| Mail list/get/attachments | yes | yes | yes | yes |
| Functions / Apps / Accounts / Queues | yes | yes | yes | yes |
| IR / usage / billing / monitoring | yes | no | yes | yes |
| Async client | `AsyncHomeCloud` | alias | `context.Context` on every call | sync v1 (`HttpClient.send`) |

## Documented safety / structural differences

| Behavior | Python / Node | Go | Java |
|----------|---------------|----|------|
| Retry 502/503/504 on `MQ.Send` / purge | yes | **no** (duplicate messages) | **no** (same as Go) |
| Retry SO upload (same object key) | yes | yes | yes (+ jitter) |
| Management create `Idempotency-Key` | not sent | **sent** | **sent** |
| Public returns | `dict` | structs | records / builders |
| `client.storage` alias | yes (prefer `so`) | **omitted** | **omitted** |
| Interactive login | on client | on client | **`HomeCloudAuth`** (new client) |
| Retry backoff | linear-ish | linear `500ms * n` | **exponential + full jitter** |

## Auth & client construction

| Capability | Python | Node | Go | Java |
|------------|--------|------|----|------|
| Access Key constructor | yes | yes | `New` / `FromCredentials` | `fromCredentials` / `builder()` |
| env + credentials file | `from_env` | `fromEnv` | `FromEnv` | `fromEnv` |
| `from_sts` + mailapi rewrite | yes | yes | `FromSTS` | `fromSts` |
| `from_function_context` | yes | yes | `FromFunctionContext` | `fromFunctionContext` |
| Console login | yes | yes | `Login` / `LoginBrowser` | `HomeCloudAuth.login` / `loginBrowser` |

Shared contract fixtures: [`testdata/contracts/`](../testdata/contracts/).
