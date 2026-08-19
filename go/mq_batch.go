package homecloud

import (
	"encoding/json"
	"fmt"
)

func entryBodyStr(value any) (string, error) {
	if s, ok := value.(string); ok {
		if s == "" {
			return "", newError("mq.send batch entry body must be non-empty")
		}
		return s, nil
	}
	raw, err := json.Marshal(value)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}

func buildMQBatchEntries(items []any) ([]map[string]any, error) {
	if len(items) < 1 || len(items) > mqBatchMax {
		return nil, newError(fmt.Sprintf("mq.send batch requires 1–%d messages", mqBatchMax))
	}
	entries := make([]map[string]any, 0, len(items))
	seen := map[string]struct{}{}
	for index, item := range items {
		var entry map[string]any
		if m, ok := item.(map[string]any); ok {
			if body, ok := m["body"].(string); ok {
				if body == "" {
					return nil, newError("mq.send batch entry body must be non-empty")
				}
				id := fmt.Sprint(index)
				if m["id"] != nil {
					id = fmt.Sprint(m["id"])
				}
				entry = map[string]any{"id": id, "body": body}
				if h := m["headers"]; h != nil {
					entry["headers"] = h
				}
			}
		}
		if entry == nil {
			body, err := entryBodyStr(item)
			if err != nil {
				return nil, err
			}
			entry = map[string]any{"id": fmt.Sprint(index), "body": body}
		}
		id := fmt.Sprint(entry["id"])
		if _, ok := seen[id]; ok {
			return nil, newError("mq.send batch entry ids must be unique")
		}
		seen[id] = struct{}{}
		entries = append(entries, entry)
	}
	return entries, nil
}
