# Python ↔ Node SDK parity

**Product expectation:** `@homecloud-platform/sdk` (Node) must support the **same capabilities** as `homecloud-sdk` (Python) for the same auth model and planes — same version tag (`v*`) ships both.

This is the target contract, not a “functions-only subset forever.”

## Auth & client construction

| Capability | Python | Node (today) | Target |
|------------|--------|--------------|--------|
| Access Key constructor | yes | yes | yes |
| `from_env` / env + credentials file | yes | — | yes |
| `from_credentials` | yes | via ctor | yes |
| `from_sts` (+ mailapi rewrite) | yes | yes | yes |
| `from_function_context` | yes | yes | yes |
| `from_profile` | yes | — | yes |
| Console `login` / `login_browser` / MFA | yes | — | yes (interactive) |
| Async client | yes | — | yes |

## Data plane — SO

| Capability | Python | Node (today) | Target |
|------------|--------|--------------|--------|
| `upload` | yes | yes | yes |
| `putJson` (JS helper) | — | yes | yes |
| `download` | yes | — | yes |
| `delete` | yes | — | yes |
| `list_objects` / `list_all_objects` | yes | — | yes |
| `head_object` / metadata | yes | — | yes |
| `get_object_uri` | yes | — | yes |
| `generate_presigned_url` | yes | — | yes |
| `sync_local_to_bucket` / `sync_bucket_to_local` | yes | — | yes |
| `delete_recursive` | yes | — | yes |
| list/create/delete buckets (console JWT) | yes | — | yes |

## Data plane — MQ

| Capability | Python | Node (today) | Target |
|------------|--------|--------------|--------|
| `send` | yes | yes | yes |
| `receive` | yes | — | yes |

## Secrets

| Capability | Python | Node (today) | Target |
|------------|--------|--------------|--------|
| get / list / plane ops as in Python | yes | `get` only | full surface |

## Mail (`mailapi` SigV1)

| Capability | Python | Node (today) | Target |
|------------|--------|--------------|--------|
| list mailboxes | yes | — | yes |
| list messages | yes | basic | yes |
| get message | yes | — | yes |
| download attachment | yes | — | yes |

## Functions / Apps / Accounts / Queues (console / CP)

| Capability | Python | Node (today) | Target |
|------------|--------|--------------|--------|
| `functions.*` (invoke, url, logs, …) | yes | — | yes |
| `apps` / `accounts` / `queues` helpers | yes | — | yes |

## Errors

| Capability | Python | Node (today) | Target |
|------------|--------|--------------|--------|
| Typed errors (`NotFoundError`, …) | yes | `HomeCloudError` only | typed subclasses |

## Current ship status

**Shipped (MVP for Functions handlers):** STS, SO upload/putJson, MQ send, Secrets get, Mail listMessages.

**Next parity slices (recommended order):**

1. SO read/list/delete/head/presign  
2. MQ receive  
3. Mail full + Secrets full  
4. Typed errors  
5. `from_env` / credentials file  
6. Functions / console management APIs  
7. Async API  

Until a row is “yes” in Node, do not document it as supported in examples.
