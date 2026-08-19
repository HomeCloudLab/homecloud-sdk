# HomeCloud Go SDK

Package: `github.com/HomeCloudLab/homecloud-sdk/go`  
ADR: [ADR-051](https://github.com/HomeCloudLab/homecloud-infra/blob/master/docs/adr/adr-051-go-sdk.md)

Same HomeCloud product contract as Python (`homecloud-sdk`) and Node (`@homecloud-platform/sdk`): SigV1 Access Keys, `~/.homecloud` credentials, typed HTTP errors. The **public API is idiomatic Go** (`context.Context`, structs, `errors.As`). It is allowed to differ structurally from Python/Node. Documented safety fixes take precedence over copying unsafe behavior (no automatic retry of `MQ.Send`).

## Install

```bash
go get github.com/HomeCloudLab/homecloud-sdk/go@v0.5.10
```

The Go module lives in this subdirectory, so published versions also need a **`go/v0.5.10`** git tag (in addition to `v0.5.10` for PyPI/npm).

## Usage

```go
package main

import (
    "context"
    "fmt"
    "log"

    "github.com/HomeCloudLab/homecloud-sdk/go"
)

func main() {
    client, err := homecloud.FromEnv()
    if err != nil {
        log.Fatal(err)
    }
    ctx := context.Background()

    if _, err := client.SO.Upload(ctx, "docs", homecloud.UploadOptions{
        FilePath: "./a.txt",
        Key:      "a.txt",
    }); err != nil {
        log.Fatal(err)
    }
    if _, err := client.MQ.Send(ctx, "orders", map[string]any{"id": 1}, nil); err != nil {
        log.Fatal(err)
    }
    fmt.Println("ok")
}
```

Explicit credentials (recommended for servers):

```go
client, err := homecloud.FromCredentials("HCAK...", "secret",
    homecloud.WithAccountID("..."),
)
```

Inside a Function (STS):

```go
client, err := homecloud.FromSTS(homecloud.STS{
    AccessKeyID:     sts.AccessKeyID,
    SecretAccessKey: sts.SecretAccessKey,
    SessionToken:    sts.SessionToken,
    ResourceType:    "so",
    BaseURL:         sts.BaseURL,
}, homecloud.WithAccountID(accountID))
```

## Errors

```go
var nf *homecloud.NotFoundError
if errors.As(err, &nf) {
    fmt.Println(nf.ResourceType, nf.Resource, nf.StatusCode)
}
```

## Retry (intentional Go difference)

GET/HEAD/PUT/DELETE and SO upload retry on 502/503/504. **`MQ.Send` does not retry** (duplicates). Management creates send `Idempotency-Key`. See [PARITY.md](../js/PARITY.md).

## Tests

```bash
cd go && go test ./...
```
