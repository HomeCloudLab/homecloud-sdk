package homecloud

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"strconv"
)

// MQ is the message-queue data plane.
type MQ struct{ c *Client }

func (m *MQ) Send(ctx context.Context, queue string, body any, opts *SendOptions) (json.RawMessage, error) {
	if err := m.c.requireAccessKey(); err != nil {
		return nil, err
	}
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if list, ok := asAnySlice(body); ok {
		if opts != nil && opts.Headers != nil {
			return nil, newError("headers= is only supported for single mq.send, not batch")
		}
		entries, err := buildMQBatchEntries(list)
		if err != nil {
			return nil, err
		}
		path := "/" + m.c.accountID + "/" + queue + "/messages/batch"
		return m.c.dataPlaneJSON(ctx, "mq", http.MethodPost, path, m.c.accountID,
			withJSON(map[string]any{"entries": entries}), withRetry(retryNever))
	}
	bodyStr, err := entryBodyStr(body)
	if err != nil {
		return nil, err
	}
	payload := map[string]any{"body": bodyStr}
	if opts != nil && opts.Headers != nil {
		payload["headers"] = opts.Headers
	}
	path := "/" + m.c.accountID + "/" + queue + "/messages"
	return m.c.dataPlaneJSON(ctx, "mq", http.MethodPost, path, m.c.accountID, withJSON(payload), withRetry(retryNever))
}

func (m *MQ) Receive(ctx context.Context, queue string, opts ReceiveOptions) ([]Message, error) {
	return m.receive(ctx, queue, "/messages", opts)
}

func (m *MQ) ReceiveDLQ(ctx context.Context, queue string, opts ReceiveOptions) ([]Message, error) {
	return m.receive(ctx, queue, "/dlq/messages", opts)
}

func (m *MQ) receive(ctx context.Context, queue, suffix string, opts ReceiveOptions) ([]Message, error) {
	if err := m.c.requireAccessKey(); err != nil {
		return nil, err
	}
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if opts.MaxMessages <= 0 {
		opts.MaxMessages = 1
	}
	if opts.WaitSeconds == 0 {
		opts.WaitSeconds = 20
	}
	q := url.Values{}
	q.Set("max_messages", strconv.Itoa(opts.MaxMessages))
	q.Set("wait_seconds", strconv.Itoa(opts.WaitSeconds))
	if opts.Delete {
		q.Set("delete", "true")
	}
	path := "/" + m.c.accountID + "/" + queue + suffix
	raw, err := m.c.dataPlaneJSON(ctx, "mq", http.MethodGet, path, m.c.accountID, withQuery(q))
	if err != nil {
		return nil, err
	}
	return itemsOf[Message](raw)
}

func (m *MQ) Delete(ctx context.Context, queue string, sequence int64) error {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return err
	}
	path := "/" + m.c.accountID + "/" + queue + "/messages/" + strconv.FormatInt(sequence, 10)
	_, err := m.c.dataPlaneJSON(ctx, "mq", http.MethodDelete, path, m.c.accountID)
	return err
}

func (m *MQ) DeleteDLQ(ctx context.Context, queue string, sequence int64) error {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return err
	}
	path := "/" + m.c.accountID + "/" + queue + "/dlq/messages/" + strconv.FormatInt(sequence, 10)
	_, err := m.c.dataPlaneJSON(ctx, "mq", http.MethodDelete, path, m.c.accountID)
	return err
}

func (m *MQ) Purge(ctx context.Context, queue string) error {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return err
	}
	path := "/" + m.c.accountID + "/" + queue + "/purge"
	_, err := m.c.dataPlaneJSON(ctx, "mq", http.MethodPost, path, m.c.accountID, withRetry(retryNever))
	return err
}

func (m *MQ) PurgeDLQ(ctx context.Context, queue string) error {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return err
	}
	path := "/" + m.c.accountID + "/" + queue + "/dlq/purge"
	_, err := m.c.dataPlaneJSON(ctx, "mq", http.MethodPost, path, m.c.accountID, withRetry(retryNever))
	return err
}

func asAnySlice(body any) ([]any, bool) {
	switch v := body.(type) {
	case []any:
		return v, true
	default:
		raw, err := json.Marshal(body)
		if err != nil {
			return nil, false
		}
		if len(raw) == 0 || raw[0] != '[' {
			return nil, false
		}
		var list []any
		if json.Unmarshal(raw, &list) != nil {
			return nil, false
		}
		return list, true
	}
}
