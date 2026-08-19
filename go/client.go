package homecloud

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

// Client is the HomeCloud SDK entry point.
type Client struct {
	accessKeyID     string
	secretAccessKey string
	accountID       string
	apex            string
	profileName     string
	sessionToken    string
	accessToken     string
	consoleBaseURL  string
	dataPlaneBases  map[string]string
	requestTimeout  time.Duration
	http            *http.Client

	SO         *SO
	MQ         *MQ
	Secrets    *Secrets
	Mail       *Mail
	Functions  *Functions
	Accounts   *Accounts
	Apps       *Apps
	Queues     *Queues
	IR         *IR
	Usage      *Usage
	Billing    *Billing
	Monitoring *Monitoring
}

func (c *Client) bind() {
	c.SO = &SO{c: c}
	c.MQ = &MQ{c: c}
	c.Secrets = &Secrets{c: c}
	c.Mail = &Mail{c: c}
	c.Functions = &Functions{c: c}
	c.Accounts = &Accounts{c: c}
	c.Apps = &Apps{c: c}
	c.Queues = &Queues{c: c}
	c.IR = &IR{c: c}
	c.Usage = &Usage{c: c}
	c.Billing = &Billing{c: c}
	c.Monitoring = &Monitoring{c: c}
}

// New builds a client. Constructor options win over env and files.
func New(opts ...Option) (*Client, error) {
	c := &Client{
		apex:           platformApex(),
		requestTimeout: defaultRequestTimeout,
		dataPlaneBases: map[string]string{},
	}
	peek := &Client{}
	for _, opt := range opts {
		opt(peek)
	}
	c.profileName = peek.profileName
	c.loadFileAndEnv()
	for _, opt := range opts {
		opt(c)
	}
	if c.apex == "" {
		c.apex = DefaultApex
	}
	if c.profileName == "" {
		c.profileName = DefaultProfile
	}
	c.bind()
	return c, nil
}

func (c *Client) loadFileAndEnv() {
	explicitProfile := c.profileName
	if explicitProfile == "" {
		explicitProfile = envProfile()
	}
	cf, err := loadCredentialsFile(credentialsPath())
	if err == nil {
		name := explicitProfile
		if name == "" {
			name = cf.DefaultProfile
		}
		if name == "" {
			name = DefaultProfile
		}
		c.profileName = name
		if p, ok := cf.Profiles[name]; ok {
			if p.Apex != "" {
				c.apex = p.Apex
			}
			c.accountID = p.DefaultAccountID
			c.accessKeyID = p.AccessKeyID
			c.secretAccessKey = p.SecretAccessKey
		}
	} else {
		c.profileName = firstNonEmpty(explicitProfile, DefaultProfile)
	}

	sessions := loadSessionFile(sessionPath())
	if s, ok := sessions[c.profileName]; ok {
		c.accessToken = s.AccessToken
		if s.ActiveAccountID != "" {
			c.accountID = s.ActiveAccountID
		} else if c.accountID == "" {
			c.accountID = s.LastUsedAccountID
		}
	}

	if v := envApex(); v != "" {
		c.apex = v
	}
	if v := envAccountID(); v != "" {
		c.accountID = v
	}
	if v := envAccessKeyID(); v != "" {
		c.accessKeyID = v
	}
	if v := envSecretAccessKey(); v != "" {
		c.secretAccessKey = v
	}
	if v := envProfile(); v != "" {
		c.profileName = v
	}
}

// FromEnv loads HOMECLOUD_* / HC_* then credentials file.
func FromEnv(opts ...Option) (*Client, error) {
	base := []Option{}
	if v := envProfile(); v != "" {
		base = append(base, WithProfile(v))
	}
	if v := envAccessKeyID(); v != "" {
		if s := envSecretAccessKey(); s != "" {
			base = append(base, WithAccessKey(v, s))
		}
	}
	if v := envAccountID(); v != "" {
		base = append(base, WithAccountID(v))
	}
	if v := envApex(); v != "" {
		base = append(base, WithApex(v))
	}
	return New(append(base, opts...)...)
}

// FromCredentials builds an explicit Access Key client (preferred for CI).
func FromCredentials(accessKeyID, secretAccessKey string, opts ...Option) (*Client, error) {
	return New(append([]Option{WithAccessKey(accessKeyID, secretAccessKey)}, opts...)...)
}

// FromProfile loads ~/.homecloud/credentials for the named profile.
func FromProfile(profile string, opts ...Option) (*Client, error) {
	return New(append([]Option{WithProfile(profile)}, opts...)...)
}

// STS is a function-runtime temporary credential entry.
type STS struct {
	AccessKeyID     string `json:"access_key_id"`
	SecretAccessKey string `json:"secret_access_key"`
	SessionToken    string `json:"session_token,omitempty"`
	BaseURL         string `json:"base_url,omitempty"`
	MailBaseURL     string `json:"mail_base_url,omitempty"`
	ResourceType    string `json:"resource_type,omitempty"`
}

// FromSTS builds a client from a function STS binding (mailapi rewrite included).
func FromSTS(sts STS, opts ...Option) (*Client, error) {
	aid := envAccountID()
	base := strings.TrimRight(sts.BaseURL, "/")
	if base == "" {
		base = strings.TrimRight(sts.MailBaseURL, "/")
	}
	resourceType := strings.ToLower(strings.TrimSpace(sts.ResourceType))
	resolvedApex := envApex()
	dataPlane := map[string]string{}

	if base != "" {
		u, _ := url.Parse(base)
		host := ""
		if u != nil {
			host = u.Hostname()
		}
		if resourceType == "mail" {
			if strings.HasPrefix(host, "console.") || strings.Contains(base, "/api/v1") {
				if strings.HasPrefix(host, "console.") {
					resolvedApex = firstNonEmpty(resolvedApex, strings.TrimPrefix(host, "console."))
				}
				if resolvedApex == "" {
					resolvedApex = DefaultApex
				}
				dataPlane["mail"] = strings.TrimRight(mailAPIURL(resolvedApex), "/")
			} else {
				dataPlane["mail"] = base
				if strings.HasPrefix(host, "mailapi.") {
					resolvedApex = firstNonEmpty(resolvedApex, strings.TrimPrefix(host, "mailapi."))
				}
			}
		} else if resourceType == "so" || resourceType == "mq" || resourceType == "secrets" {
			dataPlane[resourceType] = base
			prefix := resourceType + "."
			if strings.HasPrefix(host, prefix) {
				resolvedApex = firstNonEmpty(resolvedApex, strings.TrimPrefix(host, prefix))
			}
		}
	} else if resourceType == "mail" {
		resolvedApex = firstNonEmpty(resolvedApex, DefaultApex)
		dataPlane["mail"] = strings.TrimRight(mailAPIURL(resolvedApex), "/")
	}
	if resolvedApex == "" {
		resolvedApex = DefaultApex
	}

	baseOpts := []Option{
		WithAccessKey(sts.AccessKeyID, sts.SecretAccessKey),
		WithApex(resolvedApex),
		WithDataPlaneBases(dataPlane),
	}
	if sts.SessionToken != "" {
		baseOpts = append(baseOpts, WithSessionToken(sts.SessionToken))
	}
	if aid != "" {
		baseOpts = append(baseOpts, WithAccountID(aid))
	}
	return New(append(baseOpts, opts...)...)
}

// FunctionContext is the subset of a Function runtime context used for STS.
type FunctionContext struct {
	AccountID string         `json:"account_id"`
	STS       map[string]STS `json:"sts"`
}

// FromFunctionContext reads context.sts[binding] or HC_STS_JSON.
func FromFunctionContext(ctx *FunctionContext, binding string, opts ...Option) (*Client, error) {
	stsMap := map[string]STS{}
	if ctx != nil && ctx.STS != nil {
		stsMap = ctx.STS
	}
	if len(stsMap) == 0 {
		if raw := os.Getenv("HC_STS_JSON"); raw != "" {
			_ = json.Unmarshal([]byte(raw), &stsMap)
		}
	}
	entry, ok := stsMap[binding]
	if !ok || entry.AccessKeyID == "" {
		return nil, newError("Missing STS for binding '" + binding + "'. Set Bindings + execution_role on the function (no manual Access Key ENV needed).")
	}
	accountID := ""
	if ctx != nil {
		accountID = ctx.AccountID
	}
	if accountID == "" {
		accountID = os.Getenv("HC_ACCOUNT_ID")
	}
	if accountID != "" {
		opts = append([]Option{WithAccountID(accountID)}, opts...)
	}
	return FromSTS(entry, opts...)
}

func firstNonEmpty(vals ...string) string {
	for _, v := range vals {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

func (c *Client) requireAccessKey() error {
	if c.accessKeyID == "" || c.secretAccessKey == "" {
		return newNotConfigured()
	}
	return nil
}

func (c *Client) requireConsole() error {
	if c.accessToken == "" {
		return newNotLoggedIn()
	}
	return nil
}

func (c *Client) hasAccessKey() bool {
	return c.accessKeyID != "" && c.secretAccessKey != ""
}

func (c *Client) ensureAccountID(ctx context.Context) error {
	if c.accountID != "" {
		return nil
	}
	if err := c.requireAccessKey(); err != nil {
		return err
	}
	spec := requestSpec{
		method:    http.MethodGet,
		url:       strings.TrimRight(c.dataPlaneBase("so"), "/") + whoamiPath,
		signPath:  whoamiPath,
		accountID: whoamiAccountSentinel,
		signed:    true,
		retry:     retryIdempotent,
	}
	raw, err := c.doJSON(ctx, spec)
	if err != nil {
		return err
	}
	var body struct {
		AccountID string `json:"account_id"`
	}
	if err := json.Unmarshal(raw, &body); err != nil || body.AccountID == "" {
		return newError("whoami did not return account_id")
	}
	c.accountID = body.AccountID
	c.rememberAccount(body.AccountID)
	return nil
}

func (c *Client) rememberAccount(accountID string) {
	sessions := loadSessionFile(sessionPath())
	s := sessions[c.profileName]
	s.ActiveAccountID = accountID
	s.LastUsedAccountID = accountID
	if sessions == nil {
		sessions = map[string]profileSession{}
	}
	if c.profileName == "" {
		c.profileName = DefaultProfile
	}
	sessions[c.profileName] = s
	_ = saveSessionFile(sessionPath(), sessions)
}

// AccountID returns the resolved account id (whoami if needed).
func (c *Client) AccountID(ctx context.Context) (string, error) {
	if err := c.ensureAccountID(ctx); err != nil {
		return "", err
	}
	return c.accountID, nil
}

// Login mints a console JWT (interactive / CLI). Not for unattended automation.
func (c *Client) Login(ctx context.Context, account, username, password, mfaCode string) error {
	body := map[string]string{"account": account, "username": username, "password": password}
	if mfaCode != "" {
		body["mfa_code"] = mfaCode
	}
	raw, err := c.consoleJSON(ctx, http.MethodPost, "auth/login", false, withJSON(body), withRetry(retryNever))
	if err != nil {
		return err
	}
	var out struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.Unmarshal(raw, &out); err != nil || out.AccessToken == "" {
		return newError("Login failed")
	}
	c.accessToken = out.AccessToken
	c.persistAccessToken(out.AccessToken)
	return nil
}

// LoginBrowser starts a CLI browser/passkey login and polls until complete.
func (c *Client) LoginBrowser(ctx context.Context, opts LoginBrowserOptions) error {
	var startBody any
	if opts.MFAToken != "" {
		startBody = map[string]string{"mfa_token": opts.MFAToken}
	}
	raw, err := c.consoleJSON(ctx, http.MethodPost, "auth/cli/session", false, withJSON(startBody), withRetry(retryNever))
	if err != nil {
		return err
	}
	var start struct {
		SessionID       string `json:"session_id"`
		VerificationURI string `json:"verification_uri"`
		ExpiresIn       int    `json:"expires_in"`
		Interval        int    `json:"interval"`
	}
	if err := json.Unmarshal(raw, &start); err != nil || start.SessionID == "" || start.VerificationURI == "" {
		return newError("Failed to start browser login session")
	}
	if opts.OpenBrowser {
		_ = openBrowser(start.VerificationURI)
	}
	if opts.OnWaiting != nil {
		opts.OnWaiting(start.VerificationURI)
	}
	interval := time.Duration(start.Interval) * time.Second
	if interval < time.Second {
		interval = 2 * time.Second
	}
	if opts.PollEvery > 0 {
		interval = opts.PollEvery
	}
	expires := time.Duration(start.ExpiresIn) * time.Second
	if expires <= 0 {
		expires = 10 * time.Minute
	}
	deadline := time.Now().Add(expires)
	for time.Now().Before(deadline) {
		if err := ctx.Err(); err != nil {
			return err
		}
		poll, err := c.consoleJSON(ctx, http.MethodGet, "auth/cli/session/"+start.SessionID, false, withRetry(retryNever))
		if err != nil {
			return err
		}
		var status struct {
			Status      string `json:"status"`
			AccessToken string `json:"access_token"`
		}
		_ = json.Unmarshal(poll, &status)
		switch status.Status {
		case "complete":
			if status.AccessToken == "" {
				return newError("Browser login completed without access token")
			}
			c.accessToken = status.AccessToken
			c.persistAccessToken(status.AccessToken)
			return nil
		case "expired":
			return newError("Browser login session expired")
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(interval):
		}
	}
	return newError("Browser login timed out")
}

func (c *Client) persistAccessToken(token string) {
	sessions := loadSessionFile(sessionPath())
	if sessions == nil {
		sessions = map[string]profileSession{}
	}
	if c.profileName == "" {
		c.profileName = DefaultProfile
	}
	s := sessions[c.profileName]
	s.AccessToken = token
	sessions[c.profileName] = s
	_ = saveSessionFile(sessionPath(), sessions)
}

// Configure writes Access Keys into ~/.homecloud/credentials.
func (c *Client) Configure(accessKeyID, secretAccessKey string) error {
	name := c.profileName
	if name == "" {
		name = DefaultProfile
	}
	cf, err := loadCredentialsFile(credentialsPath())
	if err != nil {
		cf = &credentialsFile{Version: 2, DefaultProfile: name, Profiles: map[string]profileConfig{}}
	}
	cf.Profiles[name] = profileConfig{Name: name, AccessKeyID: accessKeyID, SecretAccessKey: secretAccessKey}
	cf.DefaultProfile = name
	c.accessKeyID = accessKeyID
	c.secretAccessKey = secretAccessKey
	return saveCredentialsFile(cf, credentialsPath())
}

func openBrowser(uri string) error {
	// Best-effort; stdlib-only. Failure is non-fatal for LoginBrowser.
	return nil
}
