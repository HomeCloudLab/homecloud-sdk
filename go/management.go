package homecloud

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
)

type Accounts struct{ c *Client }

func (a *Accounts) List(ctx context.Context) ([]Account, error) {
	raw, err := a.c.consoleJSON(ctx, http.MethodGet, "accounts", true)
	if err != nil {
		return nil, err
	}
	items, err := itemsOf[Account](raw)
	if err != nil {
		return nil, err
	}
	return items, nil
}

func (a *Accounts) Switch(ctx context.Context, accountRef string) error {
	accounts, err := a.List(ctx)
	if err != nil {
		return err
	}
	var match *Account
	for i := range accounts {
		acc := accounts[i]
		if acc.ID == accountRef || acc.Slug == accountRef || acc.Name == accountRef {
			match = &acc
			break
		}
	}
	if match == nil {
		return newError("Account not found: " + accountRef)
	}
	a.c.accountID = match.ID
	a.c.rememberAccount(match.ID)
	return nil
}

type Apps struct{ c *Client }

func (a *Apps) List(ctx context.Context) ([]Application, error) {
	if err := a.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := a.c.consoleJSON(ctx, http.MethodGet, "accounts/"+a.c.accountID+"/applications", true)
	if err != nil {
		return nil, err
	}
	return itemsOf[Application](raw)
}

type Queues struct{ c *Client }

func (q *Queues) List(ctx context.Context, live bool) ([]Queue, error) {
	if err := q.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	var opts []func(*requestSpec)
	if live {
		v := url.Values{}
		v.Set("live", "true")
		opts = append(opts, withQuery(v))
	}
	raw, err := q.c.consoleJSON(ctx, http.MethodGet, "accounts/"+q.c.accountID+"/queues", true, opts...)
	if err != nil {
		return nil, err
	}
	return itemsOf[Queue](raw)
}

func (q *Queues) Get(ctx context.Context, name string) (*Queue, error) {
	if err := q.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := q.c.consoleJSON(ctx, http.MethodGet, "accounts/"+q.c.accountID+"/queues/"+url.PathEscape(name), true)
	if err != nil {
		return nil, err
	}
	item, err := decode[Queue](raw)
	if err != nil {
		return nil, err
	}
	return &item, nil
}

type IR struct{ c *Client }

func (r *IR) List(ctx context.Context) (*RegistryList, error) {
	if err := r.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := r.c.consoleJSON(ctx, http.MethodGet, "accounts/"+r.c.accountID+"/registry/repositories", true)
	if err != nil {
		return nil, err
	}
	list, err := decode[RegistryList](raw)
	if err != nil {
		return nil, err
	}
	return &list, nil
}

func (r *IR) Create(ctx context.Context, name string, keepLast int) (json.RawMessage, error) {
	if err := r.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	body := map[string]any{"name": name}
	if keepLast > 0 {
		body["keep_last"] = keepLast
	}
	return r.c.consoleJSON(ctx, http.MethodPost, "accounts/"+r.c.accountID+"/registry/repositories", true,
		withJSON(body), withIdempotency(newIdempotencyKey()))
}

func (r *IR) Usage(ctx context.Context) (json.RawMessage, error) {
	if err := r.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	return r.c.consoleJSON(ctx, http.MethodGet, "accounts/"+r.c.accountID+"/registry/repositories/usage", true)
}

type Usage struct{ c *Client }

func (u *Usage) List(ctx context.Context, params url.Values) (json.RawMessage, error) {
	if err := u.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	var opts []func(*requestSpec)
	if params != nil {
		opts = append(opts, withQuery(params))
	}
	return u.c.consoleJSON(ctx, http.MethodGet, "accounts/"+u.c.accountID+"/usage", true, opts...)
}

type Billing struct{ c *Client }

func (b *Billing) get(ctx context.Context, suffix string, params url.Values) (json.RawMessage, error) {
	if err := b.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	var opts []func(*requestSpec)
	if params != nil {
		opts = append(opts, withQuery(params))
	}
	return b.c.consoleJSON(ctx, http.MethodGet, "accounts/"+b.c.accountID+"/billing"+suffix, true, opts...)
}

func (b *Billing) Summary(ctx context.Context) (json.RawMessage, error) {
	return b.get(ctx, "/summary", nil)
}

func (b *Billing) Forecast(ctx context.Context, horizon int) (json.RawMessage, error) {
	if horizon <= 0 {
		horizon = 30
	}
	q := url.Values{}
	q.Set("horizon", itoa(horizon))
	return b.get(ctx, "/forecast", q)
}

func (b *Billing) Invoices(ctx context.Context) (json.RawMessage, error) {
	return b.get(ctx, "/invoices", nil)
}

type Monitoring struct{ c *Client }

func (m *Monitoring) Workspace(ctx context.Context) (json.RawMessage, error) {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	return m.c.consoleJSON(ctx, http.MethodGet, "accounts/"+m.c.accountID+"/monitoring/workspace", true)
}

func (m *Monitoring) Dashboards(ctx context.Context) (json.RawMessage, error) {
	if err := m.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	return m.c.consoleJSON(ctx, http.MethodGet, "accounts/"+m.c.accountID+"/monitoring/dashboards", true)
}
