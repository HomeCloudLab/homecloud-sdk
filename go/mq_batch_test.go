package homecloud

import (
	"testing"
)

func TestBuildMQBatchEntries(t *testing.T) {
	entries, err := buildMQBatchEntries([]any{"a", map[string]any{"x": 1}})
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 2 {
		t.Fatalf("len %d", len(entries))
	}
	if entries[0]["body"] != "a" {
		t.Fatalf("body0 %v", entries[0]["body"])
	}
}

func TestBuildMQBatchLimits(t *testing.T) {
	if _, err := buildMQBatchEntries(nil); err == nil {
		t.Fatal("empty")
	}
	tooMany := make([]any, 11)
	for i := range tooMany {
		tooMany[i] = "x"
	}
	if _, err := buildMQBatchEntries(tooMany); err == nil {
		t.Fatal("too many")
	}
}

func TestBuildMQBatchUniqueIDs(t *testing.T) {
	_, err := buildMQBatchEntries([]any{
		map[string]any{"id": "1", "body": "a"},
		map[string]any{"id": "1", "body": "b"},
	})
	if err == nil {
		t.Fatal("expected unique id error")
	}
}

func TestSOObjectPathsEncoding(t *testing.T) {
	sign, u := soObjectPaths("acc", "docs", "folder/a file.txt")
	if sign != "/acc/docs/objects/folder/a file.txt" {
		t.Fatalf("sign %s", sign)
	}
	if u != "/acc/docs/objects/folder/a%20file.txt" {
		t.Fatalf("url %s", u)
	}
}

func TestParseSOURI(t *testing.T) {
	b, p, err := parseSOURI("so://photos/2024/")
	if err != nil {
		t.Fatal(err)
	}
	if b != "photos" || p != "2024" {
		t.Fatalf("%s %s", b, p)
	}
}
