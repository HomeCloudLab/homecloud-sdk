package homecloud

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
)

type Secrets struct{ c *Client }

func (s *Secrets) List(ctx context.Context) ([]Secret, error) {
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := s.c.consoleJSON(ctx, http.MethodGet, "accounts/"+s.c.accountID+"/secrets", true)
	if err != nil {
		return nil, err
	}
	return itemsOf[Secret](raw)
}

func (s *Secrets) Get(ctx context.Context, name string) (*Secret, error) {
	if err := s.c.requireAccessKey(); err != nil {
		return nil, err
	}
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	path := "/" + s.c.accountID + "/secrets/" + url.PathEscape(name)
	raw, err := s.c.dataPlaneJSON(ctx, "secrets", http.MethodGet, path, s.c.accountID)
	if err != nil {
		return nil, err
	}
	sec, err := decode[Secret](raw)
	if err != nil {
		return nil, err
	}
	if len(sec.Value) == 0 && len(raw) > 0 {
		sec.Value = json.RawMessage(raw)
	}
	if sec.Name == "" {
		sec.Name = name
	}
	return &sec, nil
}

type Mail struct{ c *Client }

func (m *Mail) useDataPlane() bool {
	return m.c.hasAccessKey() && m.c.dataPlaneBases["mail"] != ""
}

func (m *Mail) request(ctx context.Context, method, path string, q url.Values) (json.RawMessage, error) {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	var opts []func(*requestSpec)
	if q != nil {
		opts = append(opts, withQuery(q))
	}
	if m.useDataPlane() {
		dp := mailConsolePathToDataPlane(path, m.c.accountID)
		return m.c.dataPlaneJSON(ctx, "mail", method, dp, m.c.accountID, opts...)
	}
	if m.c.hasAccessKey() {
		return m.c.consoleSignedJSON(ctx, method, path, m.c.accountID, opts...)
	}
	return m.c.consoleJSON(ctx, method, path, true, opts...)
}

func (m *Mail) requestBytes(ctx context.Context, method, path string) ([]byte, error) {
	raw, err := m.request(ctx, method, path, nil)
	if err != nil {
		return nil, err
	}
	return []byte(raw), nil
}

func mailConsolePathToDataPlane(path, accountID string) string {
	p := stringsTrimLeftSlash(path)
	prefix := "accounts/" + accountID + "/mail/"
	if len(p) >= len(prefix) && p[:len(prefix)] == prefix {
		return "/" + accountID + "/" + p[len(prefix):]
	}
	if len(p) > len(accountID) && p[:len(accountID)+1] == accountID+"/" {
		return "/" + p
	}
	return "/" + p
}

func stringsTrimLeftSlash(s string) string {
	for len(s) > 0 && s[0] == '/' {
		s = s[1:]
	}
	return s
}

func (m *Mail) ListMailboxes(ctx context.Context) ([]Mailbox, error) {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := m.request(ctx, http.MethodGet, "accounts/"+m.c.accountID+"/mail/mailboxes", nil)
	if err != nil {
		return nil, err
	}
	return itemsOf[Mailbox](raw)
}

func (m *Mail) ListMessages(ctx context.Context, opts ListMessagesOptions) (*MailMessageList, error) {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if opts.Limit <= 0 {
		opts.Limit = 50
	}
	q := url.Values{}
	q.Set("limit", itoa(opts.Limit))
	if opts.MailboxID != "" {
		q.Set("mailbox_id", opts.MailboxID)
	}
	if opts.Folder != "" {
		q.Set("folder", opts.Folder)
	}
	if opts.Direction != "" {
		q.Set("direction", opts.Direction)
	}
	if opts.Status != "" {
		q.Set("status", opts.Status)
	}
	if opts.Search != "" {
		q.Set("search", opts.Search)
	}
	if opts.Cursor != "" {
		q.Set("cursor", opts.Cursor)
	}
	raw, err := m.request(ctx, http.MethodGet, "accounts/"+m.c.accountID+"/mail/messages", q)
	if err != nil {
		return nil, err
	}
	list, err := decode[MailMessageList](raw)
	if err != nil {
		return nil, err
	}
	return &list, nil
}

func (m *Mail) GetMessage(ctx context.Context, messageID string) (*MailMessage, error) {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := m.request(ctx, http.MethodGet, "accounts/"+m.c.accountID+"/mail/messages/"+messageID, nil)
	if err != nil {
		return nil, err
	}
	msg, err := decode[MailMessage](raw)
	if err != nil {
		return nil, err
	}
	return &msg, nil
}

func (m *Mail) DownloadAttachment(ctx context.Context, messageID, partID string) ([]byte, error) {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	return m.requestBytes(ctx, http.MethodGet, "accounts/"+m.c.accountID+"/mail/messages/"+messageID+"/attachments/"+partID)
}

type Functions struct{ c *Client }

func (f *Functions) List(ctx context.Context) ([]Function, error) {
	if err := f.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := f.c.consoleJSON(ctx, http.MethodGet, "accounts/"+f.c.accountID+"/functions", true)
	if err != nil {
		return nil, err
	}
	return itemsOf[Function](raw)
}

func (f *Functions) URL(ctx context.Context, name string) (json.RawMessage, error) {
	if err := f.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	return f.c.consoleJSON(ctx, http.MethodGet, "accounts/"+f.c.accountID+"/functions/"+name+"/url", true)
}

func (f *Functions) EnableURL(ctx context.Context, name string, opts EnableURLOptions) (json.RawMessage, error) {
	if opts.RateLimitPerMinute == 0 {
		opts.RateLimitPerMinute = 60
	}
	if err := f.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	return f.c.consoleJSON(ctx, http.MethodPost, "accounts/"+f.c.accountID+"/functions/"+name+"/url/enable", true,
		withJSON(map[string]any{"public_url_enabled": opts.Public, "rate_limit_per_minute": opts.RateLimitPerMinute}),
		withRetry(retryNever))
}

func (f *Functions) DisableURL(ctx context.Context, name string) (json.RawMessage, error) {
	if err := f.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	return f.c.consoleJSON(ctx, http.MethodPost, "accounts/"+f.c.accountID+"/functions/"+name+"/url/disable", true, withRetry(retryNever))
}

func (f *Functions) Invoke(ctx context.Context, name string, payload any) (json.RawMessage, error) {
	if err := f.c.requireAccessKey(); err != nil {
		return nil, err
	}
	if err := f.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if payload == nil {
		payload = map[string]any{}
	}
	spec := requestSpec{
		method:    http.MethodPost,
		url:       stringsTrimSlash(functionURL(name, f.c.apex)) + "/",
		signPath:  "/",
		accountID: f.c.accountID,
		signed:    true,
		jsonBody:  payload,
		retry:     retryNever,
	}
	return f.c.doJSON(ctx, spec)
}

func (f *Functions) Logs(ctx context.Context, name string) (json.RawMessage, error) {
	if err := f.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := f.c.consoleJSON(ctx, http.MethodGet, "accounts/"+f.c.accountID+"/functions/"+name+"/invocations", true)
	if err != nil {
		return nil, err
	}
	return raw, nil
}

func (f *Functions) GetInvocation(ctx context.Context, name, invocationID string) (json.RawMessage, error) {
	if err := f.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	return f.c.consoleJSON(ctx, http.MethodGet, "accounts/"+f.c.accountID+"/functions/"+name+"/invocations/"+invocationID, true)
}
