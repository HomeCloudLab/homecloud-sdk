# Python ↔ Node SDK parity

**Product expectation:** `@homecloud-platform/sdk` (Node) supports the **same capabilities** as `homecloud-sdk` (Python) for the same auth model and planes — same version tag (`v*`) ships both.

## Status (after N4b implementation)

| Area | Status |
|------|--------|
| Auth (`fromSts`, `fromFunctionContext`, `fromEnv`/`fromProfile`, `fromCredentials`, login/loginBrowser) | yes |
| Typed errors | yes |
| SO data plane + console buckets + sync | yes |
| MQ send/receive (+ batch send via list) | yes |
| Secrets get (DP) + list (console) | yes |
| Mail list/get/attachments | yes |
| Functions / Apps / Accounts / Queues | yes |
| Async naming (`AsyncHomeCloud`) | alias (Node is async-native) |

Python-only nuances still acceptable as follow-ups (not blockers):

- MFA interactive resolver UX parity during console calls
- Parallel SO sync worker pool tuning (`max_workers` / progress callbacks)
- Full CLI browser MFA edge-cases

## Auth & client construction

| Capability | Python | Node |
|------------|--------|------|
| Access Key constructor | yes | yes |
| `from_env` / env + credentials file | yes | yes (`fromEnv` / `fromProfile`) |
| `from_credentials` | yes | yes |
| `from_sts` (+ mailapi rewrite) | yes | yes |
| `from_function_context` | yes | yes |
| `from_profile` | yes | yes |
| Console `login` / `login_browser` | yes | yes |
| Async client | yes | `AsyncHomeCloud` alias |

## Data plane — SO / MQ / Secrets / Mail / Functions

Implemented to match Python method sets (camelCase in JS). See `src/so.js`, `src/mq.js`, `src/secrets.js`, `src/mail.js`, `src/management.js`.
