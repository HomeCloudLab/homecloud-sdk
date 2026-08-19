package homecloud

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestSigV1Vectors(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "testdata", "contracts", "sigv1_vectors.json"))
	if err != nil {
		t.Fatal(err)
	}
	var vectors []struct {
		Name         string `json:"name"`
		Method       string `json:"method"`
		Path         string `json:"path"`
		Timestamp    string `json:"timestamp"`
		AccountID    string `json:"account_id"`
		Secret       string `json:"secret"`
		StringToSign string `json:"string_to_sign"`
		Signature    string `json:"signature"`
	}
	if err := json.Unmarshal(raw, &vectors); err != nil {
		t.Fatal(err)
	}
	if len(vectors) == 0 {
		t.Fatal("no vectors")
	}
	for _, v := range vectors {
		t.Run(v.Name, func(t *testing.T) {
			got := BuildStringToSign(v.Method, v.Path, v.Timestamp, v.AccountID)
			if got != v.StringToSign {
				t.Fatalf("string_to_sign\n got %q\nwant %q", got, v.StringToSign)
			}
			sig := ComputeSignature(v.Secret, got)
			if sig != v.Signature {
				t.Fatalf("signature\n got %s\nwant %s", sig, v.Signature)
			}
			if len(sig) != 64 {
				t.Fatalf("signature length %d", len(sig))
			}
		})
	}
}

func TestFormatTimestampNoMicros(t *testing.T) {
	ts := FormatTimestamp(mustParseTime("2026-08-17T12:00:00.123456Z"))
	if ts != "2026-08-17T12:00:00Z" {
		t.Fatalf("got %s", ts)
	}
}
