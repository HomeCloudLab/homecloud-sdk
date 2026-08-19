// Package homecloud is the HomeCloud Go SDK (ADR-051).
//
// Behavioral parity with Python homecloud-sdk and Node @homecloud-platform/sdk:
// same SigV1, credentials chain, and HTTP error mapping. The public API is
// idiomatic Go (context.Context, typed structs, errors.As) and is allowed to
// differ structurally from Python/Node. Documented safety fixes (no automatic
// retry of MQ.Send) take precedence over copying unsafe behavior.
package homecloud

// Version matches homecloud-sdk / @homecloud-platform/sdk. Go modules also
// require git tag go/v<Version> in this subdirectory.
const Version = "0.5.10"
