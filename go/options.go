package homecloud

import (
	"net/http"
	"time"
)

// Option configures a Client.
type Option func(*Client)

func WithAccessKey(id, secret string) Option {
	return func(c *Client) {
		c.accessKeyID = id
		c.secretAccessKey = secret
	}
}

func WithAccountID(id string) Option {
	return func(c *Client) { c.accountID = id }
}

func WithApex(apex string) Option {
	return func(c *Client) { c.apex = stringsTrimSlash(apex) }
}

func WithProfile(name string) Option {
	return func(c *Client) { c.profileName = name }
}

func WithSessionToken(token string) Option {
	return func(c *Client) { c.sessionToken = token }
}

func WithAccessToken(jwt string) Option {
	return func(c *Client) { c.accessToken = jwt }
}

func WithConsoleBaseURL(u string) Option {
	return func(c *Client) { c.consoleBaseURL = stringsTrimSlash(u) }
}

func WithDataPlaneBase(service, baseURL string) Option {
	return func(c *Client) {
		if c.dataPlaneBases == nil {
			c.dataPlaneBases = map[string]string{}
		}
		c.dataPlaneBases[service] = stringsTrimSlash(baseURL)
	}
}

func WithDataPlaneBases(bases map[string]string) Option {
	return func(c *Client) {
		if c.dataPlaneBases == nil {
			c.dataPlaneBases = map[string]string{}
		}
		for k, v := range bases {
			c.dataPlaneBases[k] = stringsTrimSlash(v)
		}
	}
}

// WithRequestTimeout sets the default timeout used when the caller’s context
// has no deadline on non-streaming requests. Zero disables the SDK default.
// Streaming download/upload never apply this timeout.
func WithRequestTimeout(d time.Duration) Option {
	return func(c *Client) { c.requestTimeout = d }
}

func WithHTTPClient(httpClient *http.Client) Option {
	return func(c *Client) { c.http = httpClient }
}

func stringsTrimSlash(s string) string {
	for len(s) > 0 && (s[len(s)-1] == '/') {
		s = s[:len(s)-1]
	}
	return s
}
