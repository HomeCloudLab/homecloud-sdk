package homecloud

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestMQReceiveAndDelete(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/acc/orders/messages":
			if r.URL.Query().Get("delete") != "true" {
				t.Errorf("expected delete=true")
			}
			_ = json.NewEncoder(w).Encode(map[string]any{
				"items": []map[string]any{{"sequence": 7, "body": `{"id":1}`}},
			})
		case r.Method == http.MethodDelete && r.URL.Path == "/acc/orders/messages/7":
			w.WriteHeader(204)
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()
	c := isolatedClient(t, WithAccessKey("HCAK", "s"), WithAccountID("acc"), WithDataPlaneBase("mq", srv.URL))
	msgs, err := c.MQ.Receive(context.Background(), "orders", ReceiveOptions{MaxMessages: 10, Delete: true})
	if err != nil {
		t.Fatal(err)
	}
	if len(msgs) != 1 || msgs[0].Sequence != 7 {
		t.Fatalf("%+v", msgs)
	}
	if err := c.MQ.Delete(context.Background(), "orders", 7); err != nil {
		t.Fatal(err)
	}
}

func TestMQBatchSend(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/acc/orders/messages/batch" {
			http.NotFound(w, r)
			return
		}
		raw, _ := io.ReadAll(r.Body)
		var body struct {
			Entries []map[string]any `json:"entries"`
		}
		_ = json.Unmarshal(raw, &body)
		if len(body.Entries) != 2 {
			t.Errorf("entries %d", len(body.Entries))
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"ok": true})
	}))
	defer srv.Close()
	c := isolatedClient(t, WithAccessKey("HCAK", "s"), WithAccountID("acc"), WithDataPlaneBase("mq", srv.URL))
	_, err := c.MQ.Send(context.Background(), "orders", []any{map[string]any{"id": 1}, map[string]any{"id": 2}}, nil)
	if err != nil {
		t.Fatal(err)
	}
}

func TestCreateBucketSendsIdempotencyKey(t *testing.T) {
	var gotKey string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotKey = r.Header.Get("Idempotency-Key")
		_ = json.NewEncoder(w).Encode(map[string]any{"name": "docs", "status": "active"})
	}))
	defer srv.Close()
	c := isolatedClient(t, WithAccessToken("jwt"), WithAccountID("acc"), WithConsoleBaseURL(srv.URL))
	b, err := c.SO.CreateBucket(context.Background(), "Docs")
	if err != nil {
		t.Fatal(err)
	}
	if b.Name != "docs" {
		t.Fatalf("name %s", b.Name)
	}
	if gotKey == "" {
		t.Fatal("missing Idempotency-Key")
	}
}

func TestLoginStoresToken(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"access_token": "tok-1"})
	}))
	defer srv.Close()
	c := isolatedClient(t, WithConsoleBaseURL(srv.URL))
	if err := c.Login(context.Background(), "100", "alice", "pw", ""); err != nil {
		t.Fatal(err)
	}
	if c.accessToken != "tok-1" {
		t.Fatalf("token %s", c.accessToken)
	}
}

func TestSecretsGet(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"name": "db", "value": "s3cret"})
	}))
	defer srv.Close()
	c := isolatedClient(t, WithAccessKey("HCAK", "s"), WithAccountID("acc"), WithDataPlaneBase("secrets", srv.URL))
	sec, err := c.Secrets.Get(context.Background(), "db")
	if err != nil {
		t.Fatal(err)
	}
	if sec.Name != "db" {
		t.Fatalf("%s", sec.Name)
	}
}
