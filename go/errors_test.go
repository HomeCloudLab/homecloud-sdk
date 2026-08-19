package homecloud

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestErrorFromStatusContract(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("..", "testdata", "contracts", "error_from_status.json"))
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Name         string `json:"name"`
		Status       int    `json:"status"`
		Detail       any    `json:"detail"`
		URL          string `json:"url"`
		Type         string `json:"type"`
		ResourceType string `json:"resource_type"`
		Resource     string `json:"resource"`
		ErrorCode    string `json:"error_code"`
	}
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	for _, tc := range cases {
		t.Run(tc.Name, func(t *testing.T) {
			err := ErrorFromStatus(tc.Status, tc.Detail, tc.URL)
			if err == nil {
				t.Fatal("expected error")
			}
			switch tc.Type {
			case "NotFoundError":
				var nf *NotFoundError
				if !errors.As(err, &nf) {
					t.Fatalf("got %T", err)
				}
				if nf.ResourceType != tc.ResourceType {
					t.Fatalf("resource_type %q want %q", nf.ResourceType, tc.ResourceType)
				}
				if nf.Resource != tc.Resource {
					t.Fatalf("resource %q want %q", nf.Resource, tc.Resource)
				}
				if !IsNotFound(err) {
					t.Fatal("IsNotFound")
				}
				var api *APIError
				if !errors.As(err, &api) {
					t.Fatal("Unwrap to APIError")
				}
			case "UnauthorizedError":
				var u *UnauthorizedError
				if !errors.As(err, &u) {
					t.Fatalf("got %T", err)
				}
			case "PermissionDeniedError":
				var p *PermissionDeniedError
				if !errors.As(err, &p) {
					t.Fatalf("got %T", err)
				}
				if tc.ErrorCode != "" && p.ErrorCode() != tc.ErrorCode {
					t.Fatalf("code %q", p.ErrorCode())
				}
			case "BadRequestError":
				var b *BadRequestError
				if !errors.As(err, &b) {
					t.Fatalf("got %T", err)
				}
			case "ConflictError":
				var c *ConflictError
				if !errors.As(err, &c) {
					t.Fatalf("got %T", err)
				}
			case "RateLimitError":
				var r *RateLimitError
				if !errors.As(err, &r) {
					t.Fatalf("got %T", err)
				}
			case "ServiceUnavailableError":
				var s *ServiceUnavailableError
				if !errors.As(err, &s) {
					t.Fatalf("got %T", err)
				}
			default:
				t.Fatalf("unknown type %s", tc.Type)
			}
		})
	}
}
