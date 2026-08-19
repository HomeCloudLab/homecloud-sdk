package homecloud

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func isolatedClient(t *testing.T, opts ...Option) *Client {
	t.Helper()
	t.Setenv("HOMECLOUD_CONFIG_DIR", t.TempDir())
	t.Setenv("HOMECLOUD_ACCESS_KEY_ID", "")
	t.Setenv("HC_ACCESS_KEY_ID", "")
	t.Setenv("HOMECLOUD_SECRET_ACCESS_KEY", "")
	t.Setenv("HC_SECRET_ACCESS_KEY", "")
	t.Setenv("HOMECLOUD_ACCOUNT_ID", "")
	t.Setenv("HC_ACCOUNT_ID", "")
	t.Setenv("HOMECLOUD_APEX", "")
	t.Setenv("HC_APEX", "")
	t.Setenv("HOMECLOUD_PROFILE", "")
	c, err := New(opts...)
	if err != nil {
		t.Fatal(err)
	}
	return c
}

func TestFromSTSMailRewrite(t *testing.T) {
	t.Setenv("HOMECLOUD_CONFIG_DIR", t.TempDir())
	t.Setenv("HC_ACCOUNT_ID", "acc-1")
	c, err := FromSTS(STS{
		AccessKeyID:     "HCAKTEST",
		SecretAccessKey: "secret",
		ResourceType:    "mail",
		BaseURL:         "https://console.holab.abrdns.com/api/v1",
	})
	if err != nil {
		t.Fatal(err)
	}
	if c.dataPlaneBases["mail"] != "https://mailapi.holab.abrdns.com" {
		t.Fatalf("mail base %q", c.dataPlaneBases["mail"])
	}
	if c.apex != "holab.abrdns.com" {
		t.Fatalf("apex %q", c.apex)
	}
	if c.accountID != "acc-1" {
		t.Fatalf("account %q", c.accountID)
	}
}

func TestFromFunctionContext(t *testing.T) {
	t.Setenv("HOMECLOUD_CONFIG_DIR", t.TempDir())
	c, err := FromFunctionContext(&FunctionContext{
		AccountID: "acc-9",
		STS: map[string]STS{
			"archive": {
				AccessKeyID:     "HCAK",
				SecretAccessKey: "s",
				ResourceType:    "so",
				BaseURL:         "https://so.example.test",
			},
		},
	}, "archive")
	if err != nil {
		t.Fatal(err)
	}
	if c.dataPlaneBases["so"] != "https://so.example.test" {
		t.Fatalf("so base %s", c.dataPlaneBases["so"])
	}
	if c.accountID != "acc-9" {
		t.Fatal(c.accountID)
	}
}

func TestGETRetriesOn503(t *testing.T) {
	var hits atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n := hits.Add(1)
		if n < 3 {
			w.WriteHeader(503)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"key":"a.txt","size":1}`))
	}))
	defer srv.Close()
	c := isolatedClient(t,
		WithAccessKey("HCAK", "secret"),
		WithAccountID("acc"),
		WithDataPlaneBase("so", srv.URL),
		WithRequestTimeout(5*time.Second),
	)
	head, err := c.SO.HeadObject(context.Background(), "docs", "a.txt")
	if err != nil {
		t.Fatal(err)
	}
	if head.Key != "a.txt" {
		t.Fatalf("key %s", head.Key)
	}
	if hits.Load() != 3 {
		t.Fatalf("hits %d", hits.Load())
	}
}

func TestMQSendDoesNotRetry503(t *testing.T) {
	var hits atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits.Add(1)
		w.WriteHeader(503)
	}))
	defer srv.Close()
	c := isolatedClient(t,
		WithAccessKey("HCAK", "secret"),
		WithAccountID("acc"),
		WithDataPlaneBase("mq", srv.URL),
		WithRequestTimeout(5*time.Second),
	)
	_, err := c.MQ.Send(context.Background(), "orders", map[string]any{"id": 1}, nil)
	if err == nil {
		t.Fatal("expected error")
	}
	var unavail *ServiceUnavailableError
	if !errors.As(err, &unavail) {
		t.Fatalf("got %T %v", err, err)
	}
	if hits.Load() != 1 {
		t.Fatalf("hits %d want 1", hits.Load())
	}
}

func TestSOUploadAndList(t *testing.T) {
	objects := map[string][]byte{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && strings.Contains(r.URL.Path, "/objects") && !strings.Contains(r.URL.Path, "/copy"):
			if err := r.ParseMultipartForm(1 << 20); err != nil {
				http.Error(w, err.Error(), 400)
				return
			}
			key := r.FormValue("key")
			f, _, err := r.FormFile("file")
			if err != nil {
				http.Error(w, err.Error(), 400)
				return
			}
			defer f.Close()
			b, _ := io.ReadAll(f)
			objects[key] = b
			_ = json.NewEncoder(w).Encode(map[string]any{"key": key, "size": len(b)})
		case r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/metadata"):
			_ = json.NewEncoder(w).Encode(map[string]any{"key": "a.txt", "size": 4, "etag": "abc", "content_type": "text/plain", "metadata": map[string]any{}, "tags": map[string]any{}})
		case r.Method == http.MethodGet && strings.Contains(r.URL.Path, "/objects") && r.URL.Query().Get("prefix") != "skip":
			_ = json.NewEncoder(w).Encode(map[string]any{
				"items":    []map[string]any{{"key": "a.txt", "size": 4, "is_dir": false}},
				"has_more": false,
			})
		case r.Method == http.MethodDelete:
			w.WriteHeader(204)
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()
	c := isolatedClient(t,
		WithAccessKey("HCAK", "secret"),
		WithAccountID("acc"),
		WithDataPlaneBase("so", srv.URL),
	)
	ctx := context.Background()
	ref, err := c.SO.PutJSON(ctx, "docs", "a.json", map[string]any{"ok": true})
	if err != nil {
		t.Fatal(err)
	}
	if ref.Key != "a.json" {
		t.Fatalf("key %s", ref.Key)
	}
	listed, err := c.SO.ListObjects(ctx, "docs", ListObjectsOptions{Prefix: "a"})
	if err != nil {
		t.Fatal(err)
	}
	if len(listed.Items) != 1 {
		t.Fatalf("items %d", len(listed.Items))
	}
	head, err := c.SO.HeadObject(ctx, "docs", "a.txt")
	if err != nil {
		t.Fatal(err)
	}
	if head.Size != 4 {
		t.Fatalf("size %d", head.Size)
	}
}

func TestNotConfigured(t *testing.T) {
	c := isolatedClient(t)
	_, err := c.SO.HeadObject(context.Background(), "docs", "x")
	var nc *NotConfiguredError
	if !errors.As(err, &nc) {
		t.Fatalf("got %T %v", err, err)
	}
}

func Test404ObjectHint(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(404)
		_, _ = w.Write([]byte(`{"detail":{"message":"NoSuchKey"}}`))
	}))
	defer srv.Close()
	c := isolatedClient(t, WithAccessKey("HCAK", "s"), WithAccountID("acc"), WithDataPlaneBase("so", srv.URL))
	_, err := c.SO.HeadObject(context.Background(), "docs", "a.txt")
	var nf *NotFoundError
	if !errors.As(err, &nf) {
		t.Fatalf("got %T %v", err, err)
	}
	if nf.ResourceType != "object" {
		t.Fatalf("type %s", nf.ResourceType)
	}
}

func TestCredentialsRoundTrip(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("HOMECLOUD_CONFIG_DIR", dir)
	t.Setenv("HOMECLOUD_ACCESS_KEY_ID", "")
	t.Setenv("HC_ACCESS_KEY_ID", "")
	c, err := New()
	if err != nil {
		t.Fatal(err)
	}
	if err := c.Configure("HCAKFILE", "supersecret"); err != nil {
		t.Fatal(err)
	}
	c2, err := FromProfile("default")
	if err != nil {
		t.Fatal(err)
	}
	if c2.accessKeyID != "HCAKFILE" || c2.secretAccessKey != "supersecret" {
		t.Fatalf("loaded %+v", c2.accessKeyID)
	}
}

func TestUserContextDeadlineWins(t *testing.T) {
	started := make(chan struct{})
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		close(started)
		time.Sleep(200 * time.Millisecond)
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`{}`))
	}))
	defer srv.Close()
	c := isolatedClient(t,
		WithAccessKey("HCAK", "s"),
		WithAccountID("acc"),
		WithDataPlaneBase("so", srv.URL),
		WithRequestTimeout(30*time.Second),
	)
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	_, err := c.SO.HeadObject(ctx, "docs", "a.txt")
	if err == nil {
		t.Fatal("expected timeout")
	}
}

func mustParseTime(s string) time.Time {
	tm, err := time.Parse(time.RFC3339Nano, s)
	if err != nil {
		panic(err)
	}
	return tm
}
