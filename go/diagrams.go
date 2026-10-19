package homecloud

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
)

// Diagrams is account architecture diagrams (management plane).
type Diagrams struct{ c *Client }

func (d *Diagrams) request(ctx context.Context, method, path string, opts ...func(*requestSpec)) (json.RawMessage, error) {
	if err := d.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if d.c.hasAccessKey() {
		return d.c.consoleSignedJSON(ctx, method, path, d.c.accountID, opts...)
	}
	return d.c.consoleJSON(ctx, method, path, true, opts...)
}

func (d *Diagrams) List(ctx context.Context) ([]map[string]any, error) {
	raw, err := d.request(ctx, http.MethodGet, "accounts/"+d.c.accountID+"/diagrams")
	if err != nil {
		return nil, err
	}
	return itemsOf[map[string]any](raw)
}

func (d *Diagrams) Get(ctx context.Context, diagramID string) (map[string]any, error) {
	raw, err := d.request(ctx, http.MethodGet, "accounts/"+d.c.accountID+"/diagrams/"+url.PathEscape(diagramID))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (d *Diagrams) Create(ctx context.Context, name string, description string, document map[string]any) (map[string]any, error) {
	body := map[string]any{"name": name}
	if description != "" {
		body["description"] = description
	}
	if document != nil {
		body["document"] = document
	}
	raw, err := d.request(ctx, http.MethodPost, "accounts/"+d.c.accountID+"/diagrams", withJSON(body))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (d *Diagrams) Update(ctx context.Context, diagramID string, fields map[string]any) (map[string]any, error) {
	raw, err := d.request(ctx, http.MethodPatch, "accounts/"+d.c.accountID+"/diagrams/"+url.PathEscape(diagramID), withJSON(fields))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}
