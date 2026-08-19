# Shared SDK contract fixtures

Used by the Go SDK tests today; Python/Node should load the same files when cheap.

| File | Purpose |
|------|---------|
| `sigv1_vectors.json` | Frozen HMAC-SHA256 vectors (also used by terraform-provider-homecloud) |
| `error_from_status.json` | HTTP status → typed error mapping (Python `error_from_status`) |
