package homecloud

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

type retryMode int

const (
	retryIdempotent retryMode = iota
	retryUpload
	retryIfIdempotency
	retryNever
)

type requestSpec struct {
	method         string
	url            string
	signPath       string
	accountID      string
	headers        map[string]string
	jsonBody       any
	query          url.Values
	multipartKey   string
	multipartFile  string
	multipartName  string
	multipartMIME  string
	multipartBytes []byte
	rawBody        io.Reader
	contentType    string
	retry          retryMode
	idempotencyKey string
	stream         bool
	expectBytes    bool
	signed         bool
	bearer         bool
}

func (c *Client) httpClient() *http.Client {
	if c.http != nil {
		return c.http
	}
	c.http = &http.Client{
		Transport: &http.Transport{
			Proxy:                 http.ProxyFromEnvironment,
			TLSHandshakeTimeout:   30 * time.Second,
			ResponseHeaderTimeout: 30 * time.Second,
			IdleConnTimeout:       90 * time.Second,
		},
	}
	return c.http
}

func (c *Client) applyTimeout(ctx context.Context, stream bool) (context.Context, context.CancelFunc) {
	if stream {
		return ctx, func() {}
	}
	if _, ok := ctx.Deadline(); ok {
		return ctx, func() {}
	}
	if c.requestTimeout <= 0 {
		return ctx, func() {}
	}
	return context.WithTimeout(ctx, c.requestTimeout)
}

func retryableStatus(code int) bool {
	return code == 502 || code == 503 || code == 504
}

func (s requestSpec) allowsRetry() bool {
	switch s.retry {
	case retryNever:
		return false
	case retryIfIdempotency:
		return s.idempotencyKey != ""
	case retryUpload, retryIdempotent:
		return true
	default:
		m := strings.ToUpper(s.method)
		return m == http.MethodGet || m == http.MethodHead || m == http.MethodPut || m == http.MethodDelete
	}
}

func (c *Client) doJSON(ctx context.Context, spec requestSpec) (json.RawMessage, error) {
	spec.expectBytes = false
	raw, err := c.do(ctx, spec)
	return json.RawMessage(raw), err
}

func (c *Client) do(ctx context.Context, spec requestSpec) ([]byte, error) {
	ctx, cancel := c.applyTimeout(ctx, spec.stream)
	defer cancel()

	var lastErr error
	for attempt := 0; attempt <= maxRetries; attempt++ {
		body, contentType, replayable, err := spec.buildBody()
		if err != nil {
			return nil, err
		}
		req, err := http.NewRequestWithContext(ctx, spec.method, spec.url, body)
		if err != nil {
			return nil, newError("Request failed: " + err.Error())
		}
		if spec.query != nil {
			req.URL.RawQuery = spec.query.Encode()
		}
		if contentType != "" {
			req.Header.Set("Content-Type", contentType)
		}
		for k, v := range spec.headers {
			req.Header.Set(k, v)
		}
		if spec.signed {
			account := spec.accountID
			if account == "" {
				account = c.accountID
			}
			for k, v := range signHeaders(c.accessKeyID, c.secretAccessKey, spec.method, spec.signPath, account, time.Now(), c.sessionToken) {
				req.Header.Set(k, v)
			}
		}
		if spec.bearer && c.accessToken != "" {
			req.Header.Set("Authorization", "Bearer "+c.accessToken)
		}
		if spec.idempotencyKey != "" {
			req.Header.Set(HeaderIdempotency, spec.idempotencyKey)
		}

		resp, err := c.httpClient().Do(req)
		if err != nil {
			lastErr = newError("Request failed: " + err.Error())
			if attempt == maxRetries || !spec.allowsRetry() || ctx.Err() != nil {
				return nil, lastErr
			}
			if err := sleepBackoff(ctx, attempt); err != nil {
				return nil, lastErr
			}
			continue
		}

		if retryableStatus(resp.StatusCode) && attempt < maxRetries && spec.allowsRetry() {
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
			if !replayable && spec.retry != retryUpload {
				return nil, ErrorFromStatus(resp.StatusCode, nil, req.URL.String())
			}
			lastErr = ErrorFromStatus(resp.StatusCode, nil, req.URL.String())
			if err := sleepBackoff(ctx, attempt); err != nil {
				return nil, lastErr
			}
			continue
		}

		raw, readErr := io.ReadAll(resp.Body)
		_ = resp.Body.Close()
		if readErr != nil {
			return nil, newError("Request failed: " + readErr.Error())
		}
		if spec.method == http.MethodDelete && resp.StatusCode == http.StatusNoContent {
			return nil, nil
		}
		if resp.StatusCode >= 400 {
			return nil, errorFromBody(resp.StatusCode, raw, req.URL.String())
		}
		return raw, nil
	}
	if lastErr != nil {
		return nil, lastErr
	}
	return nil, newError("Request failed")
}

func (s requestSpec) buildBody() (io.Reader, string, bool, error) {
	if s.multipartFile != "" || s.multipartBytes != nil {
		var buf bytes.Buffer
		mw := multipart.NewWriter(&buf)
		if err := mw.WriteField("key", s.multipartKey); err != nil {
			return nil, "", false, err
		}
		part, err := mw.CreateFormFile("file", s.multipartName)
		if err != nil {
			return nil, "", false, err
		}
		if s.multipartBytes != nil {
			if _, err := part.Write(s.multipartBytes); err != nil {
				return nil, "", false, err
			}
		} else {
			f, err := os.Open(s.multipartFile)
			if err != nil {
				return nil, "", false, newError("File not found: " + s.multipartFile)
			}
			defer f.Close()
			if _, err := io.Copy(part, f); err != nil {
				return nil, "", false, err
			}
		}
		if err := mw.Close(); err != nil {
			return nil, "", false, err
		}
		return &buf, mw.FormDataContentType(), true, nil
	}
	if s.jsonBody != nil {
		raw, err := json.Marshal(s.jsonBody)
		if err != nil {
			return nil, "", false, err
		}
		return bytes.NewReader(raw), "application/json", true, nil
	}
	if s.rawBody != nil {
		return s.rawBody, s.contentType, false, nil
	}
	return nil, s.contentType, true, nil
}

func sleepBackoff(ctx context.Context, attempt int) error {
	d := 500 * time.Millisecond * time.Duration(attempt+1)
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

func errorFromBody(status int, raw []byte, rawURL string) error {
	var detail any
	if len(bytes.TrimSpace(raw)) > 0 {
		var parsed any
		if json.Unmarshal(raw, &parsed) == nil {
			if m, ok := parsed.(map[string]any); ok {
				if d, exists := m["detail"]; exists {
					detail = d
				} else {
					detail = parsed
				}
			} else {
				detail = parsed
			}
		} else {
			detail = string(raw)
		}
	}
	return ErrorFromStatus(status, detail, rawURL)
}

func (c *Client) dataPlaneBase(service string) string {
	if c.dataPlaneBases != nil {
		if u := c.dataPlaneBases[service]; u != "" {
			return strings.TrimRight(u, "/")
		}
	}
	switch service {
	case "so":
		return soURL(c.apex)
	case "mq":
		return mqURL(c.apex)
	case "secrets":
		return secretsURL(c.apex)
	case "mail":
		return mailAPIURL(c.apex)
	default:
		return soURL(c.apex)
	}
}

func (c *Client) consoleBase() string {
	if c.consoleBaseURL != "" {
		return strings.TrimRight(c.consoleBaseURL, "/")
	}
	return strings.TrimRight(consoleURL(c.apex), "/")
}

func (c *Client) dataPlaneJSON(ctx context.Context, service, method, signPath, accountID string, opts ...func(*requestSpec)) (json.RawMessage, error) {
	if err := c.requireAccessKey(); err != nil {
		return nil, err
	}
	if err := c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if accountID == "" {
		accountID = c.accountID
	}
	spec := requestSpec{
		method:    method,
		url:       c.dataPlaneBase(service) + signPath,
		signPath:  signPath,
		accountID: accountID,
		signed:    true,
		retry:     retryFromMethod(method),
	}
	for _, o := range opts {
		o(&spec)
	}
	if spec.url == c.dataPlaneBase(service)+signPath && spec.signPath != signPath {
		spec.url = c.dataPlaneBase(service) + spec.signPath
	}
	return c.doJSON(ctx, spec)
}

func retryFromMethod(method string) retryMode {
	switch strings.ToUpper(method) {
	case http.MethodGet, http.MethodHead, http.MethodPut, http.MethodDelete:
		return retryIdempotent
	default:
		return retryNever
	}
}

func withURLPath(urlPath string) func(*requestSpec) {
	return func(s *requestSpec) {
		if urlPath == "" {
			return
		}
		u, err := url.Parse(s.url)
		if err != nil {
			return
		}
		s.url = u.Scheme + "://" + u.Host + urlPath
	}
}

func withJSON(body any) func(*requestSpec) {
	return func(s *requestSpec) { s.jsonBody = body }
}

func withQuery(q url.Values) func(*requestSpec) {
	return func(s *requestSpec) { s.query = q }
}

func withRetry(mode retryMode) func(*requestSpec) {
	return func(s *requestSpec) { s.retry = mode }
}

func withIdempotency(key string) func(*requestSpec) {
	return func(s *requestSpec) {
		s.idempotencyKey = key
		if key != "" {
			s.retry = retryIfIdempotency
		}
	}
}

func (c *Client) consoleJSON(ctx context.Context, method, pathSeg string, requireAuth bool, opts ...func(*requestSpec)) (json.RawMessage, error) {
	if requireAuth {
		if err := c.requireConsole(); err != nil {
			return nil, err
		}
	}
	rel := strings.TrimLeft(pathSeg, "/")
	spec := requestSpec{
		method: method,
		url:    c.consoleBase() + "/" + rel,
		bearer: requireAuth,
		retry:  retryFromMethod(method),
	}
	for _, o := range opts {
		o(&spec)
	}
	return c.doJSON(ctx, spec)
}

func (c *Client) consoleSignedJSON(ctx context.Context, method, pathSeg, accountID string, opts ...func(*requestSpec)) (json.RawMessage, error) {
	if err := c.requireAccessKey(); err != nil {
		return nil, err
	}
	rel := strings.TrimLeft(pathSeg, "/")
	signPath := "/api/v1/" + rel
	spec := requestSpec{
		method:    method,
		url:       c.consoleBase() + "/" + rel,
		signPath:  signPath,
		accountID: accountID,
		signed:    true,
		retry:     retryFromMethod(method),
	}
	for _, o := range opts {
		o(&spec)
	}
	return c.doJSON(ctx, spec)
}

func newIdempotencyKey() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func guessContentType(name string) string {
	ext := strings.ToLower(filepath.Ext(name))
	switch ext {
	case ".mp4":
		return "video/mp4"
	case ".json":
		return "application/json"
	case ".txt":
		return "text/plain"
	case ".png":
		return "image/png"
	case ".jpg", ".jpeg":
		return "image/jpeg"
	case ".gif":
		return "image/gif"
	case ".webp":
		return "image/webp"
	case ".pdf":
		return "application/pdf"
	case ".html", ".htm":
		return "text/html"
	case ".csv":
		return "text/csv"
	case ".zip":
		return "application/zip"
	default:
		return "application/octet-stream"
	}
}

func itemsOf[T any](raw json.RawMessage) ([]T, error) {
	if len(raw) == 0 {
		return nil, nil
	}
	var env struct {
		Items []T `json:"items"`
	}
	if err := json.Unmarshal(raw, &env); err == nil && env.Items != nil {
		return env.Items, nil
	}
	var list []T
	if err := json.Unmarshal(raw, &list); err == nil {
		return list, nil
	}
	if err := json.Unmarshal(raw, &env); err != nil {
		return nil, err
	}
	return env.Items, nil
}

func decode[T any](raw json.RawMessage) (T, error) {
	var v T
	if len(raw) == 0 {
		return v, nil
	}
	err := json.Unmarshal(raw, &v)
	return v, err
}

func jsonInt64(v any) int64 {
	switch t := v.(type) {
	case float64:
		return int64(t)
	case json.Number:
		n, _ := t.Int64()
		return n
	case int64:
		return t
	case int:
		return int64(t)
	default:
		return 0
	}
}
