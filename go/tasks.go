package homecloud

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"strings"
)

// Tasks is the account Tasks tracker (management plane — JWT or user-bound SigV1).
type Tasks struct {
	c             *Client
	actorUserID   string
	peopleCache   []map[string]any
	peopleCached  bool
}

func (t *Tasks) request(ctx context.Context, method, path string, opts ...func(*requestSpec)) (json.RawMessage, error) {
	if err := t.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if t.c.hasAccessKey() {
		return t.c.consoleSignedJSON(ctx, method, path, t.c.accountID, opts...)
	}
	return t.c.consoleJSON(ctx, method, path, true, opts...)
}

func (t *Tasks) Actor(ctx context.Context) (map[string]any, error) {
	if err := t.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	var (
		raw json.RawMessage
		err error
	)
	if t.c.hasAccessKey() {
		// Console whoami SigV1 uses sentinel "-", not the resolved account id.
		raw, err = t.c.consoleSignedJSON(ctx, http.MethodGet, "access-key/whoami", whoamiAccountSentinel)
	} else {
		raw, err = t.c.consoleJSON(ctx, http.MethodGet, "me", true)
	}
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) ActorUserID(ctx context.Context) (string, error) {
	if t.actorUserID != "" {
		return t.actorUserID, nil
	}
	info, err := t.Actor(ctx)
	if err != nil {
		return "", err
	}
	uid, _ := info["id"].(string)
	if uid == "" {
		uid, _ = info["principal_id"].(string)
	}
	if uid == "" {
		return "", newError("Could not resolve current user id — use login or a user-bound Access Key")
	}
	t.actorUserID = uid
	return uid, nil
}

func (t *Tasks) People(ctx context.Context) ([]map[string]any, error) {
	if t.peopleCached {
		return t.peopleCache, nil
	}
	raw, err := t.request(ctx, http.MethodGet, "accounts/"+t.c.accountID+"/tasks/people")
	if err != nil {
		return nil, err
	}
	items, err := itemsOf[map[string]any](raw)
	if err != nil {
		return nil, err
	}
	t.peopleCache = items
	t.peopleCached = true
	return items, nil
}

func looksLikeUUID(s string) bool {
	if len(s) != 36 {
		return false
	}
	for i, r := range s {
		switch i {
		case 8, 13, 18, 23:
			if r != '-' {
				return false
			}
		default:
			if (r < '0' || r > '9') && (r < 'a' || r > 'f') && (r < 'A' || r > 'F') {
				return false
			}
		}
	}
	return true
}

func (t *Tasks) ResolveUser(ctx context.Context, ref string) (string, error) {
	raw := strings.TrimLeft(strings.TrimSpace(ref), "@")
	if raw == "" {
		return "", newError("empty user reference")
	}
	if strings.EqualFold(raw, "me") {
		return t.ActorUserID(ctx)
	}
	if looksLikeUUID(raw) {
		return raw, nil
	}
	people, err := t.People(ctx)
	if err != nil {
		return "", err
	}
	lower := strings.ToLower(raw)
	for _, p := range people {
		u, _ := p["username"].(string)
		if strings.ToLower(u) == lower {
			id, _ := p["id"].(string)
			if id != "" {
				return id, nil
			}
		}
	}
	return "", newError("Unknown user: " + ref)
}

// TaskListOptions filters GET …/tasks/items.
type TaskListOptions struct {
	Type      string
	Status    string
	Assignee  string
	Watcher   string
	Label     string
	ProjectID string
	Q         string
	Due       string
	Archived  bool
}

func (t *Tasks) List(ctx context.Context, opts TaskListOptions) ([]map[string]any, error) {
	if err := t.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	q := url.Values{}
	q.Set("archived", "false")
	if opts.Archived {
		q.Set("archived", "true")
	}
	if opts.Type != "" {
		q.Set("type", opts.Type)
	}
	if opts.Status != "" {
		q.Set("status", opts.Status)
	}
	if opts.Assignee != "" {
		q.Set("assignee", opts.Assignee)
	}
	if opts.Watcher != "" {
		q.Set("watcher", opts.Watcher)
	}
	if opts.Label != "" {
		q.Set("label", opts.Label)
	}
	if opts.ProjectID != "" {
		q.Set("project_id", opts.ProjectID)
	}
	if opts.Q != "" {
		q.Set("q", opts.Q)
	}
	if opts.Due != "" {
		q.Set("due", opts.Due)
	}
	raw, err := t.request(ctx, http.MethodGet, "accounts/"+t.c.accountID+"/tasks/items", withQuery(q))
	if err != nil {
		return nil, err
	}
	return itemsOf[map[string]any](raw)
}

func (t *Tasks) Search(ctx context.Context, query string, opts TaskListOptions) ([]map[string]any, error) {
	opts.Q = query
	return t.List(ctx, opts)
}

func (t *Tasks) Get(ctx context.Context, key string) (map[string]any, error) {
	raw, err := t.request(ctx, http.MethodGet, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

// TaskCreateOptions for POST …/tasks/items.
type TaskCreateOptions struct {
	Type               string
	Description        string
	DescriptionFormat  string
	Assignees          []string // usernames / me / UUIDs
	DueAt              string
	ProjectID          string
	Priority           string
	Severity           string
	Services           []string
	LabelNames         []string
}

func (t *Tasks) Create(ctx context.Context, title string, opts TaskCreateOptions) (map[string]any, error) {
	body := map[string]any{"title": title, "type": "task"}
	if opts.Type != "" {
		body["type"] = opts.Type
	}
	if opts.Description != "" {
		body["description"] = opts.Description
	}
	if opts.DescriptionFormat != "" {
		body["description_format"] = opts.DescriptionFormat
	}
	if len(opts.Assignees) > 0 {
		ids := make([]string, 0, len(opts.Assignees))
		for _, a := range opts.Assignees {
			id, err := t.ResolveUser(ctx, a)
			if err != nil {
				return nil, err
			}
			ids = append(ids, id)
		}
		body["assignee_user_ids"] = ids
	}
	if opts.DueAt != "" {
		body["due_at"] = opts.DueAt
	}
	if opts.ProjectID != "" {
		body["project_id"] = opts.ProjectID
	}
	if opts.Priority != "" {
		body["priority"] = opts.Priority
	}
	if opts.Severity != "" {
		body["severity"] = opts.Severity
	}
	if opts.Services != nil {
		body["services"] = opts.Services
	}
	if opts.LabelNames != nil {
		body["label_names"] = opts.LabelNames
	}
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/items", withJSON(body))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) Update(ctx context.Context, key string, fields map[string]any) (map[string]any, error) {
	body := map[string]any{}
	for k, v := range fields {
		body[k] = v
	}
	if refs, ok := body["assignees"]; ok {
		delete(body, "assignees")
		switch typed := refs.(type) {
		case []string:
			ids := make([]string, 0, len(typed))
			for _, a := range typed {
				id, err := t.ResolveUser(ctx, a)
				if err != nil {
					return nil, err
				}
				ids = append(ids, id)
			}
			body["assignee_user_ids"] = ids
		case []any:
			ids := make([]string, 0, len(typed))
			for _, a := range typed {
				s, _ := a.(string)
				id, err := t.ResolveUser(ctx, s)
				if err != nil {
					return nil, err
				}
				ids = append(ids, id)
			}
			body["assignee_user_ids"] = ids
		}
	}
	raw, err := t.request(ctx, http.MethodPatch, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key), withJSON(body))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) Assign(ctx context.Context, key string, users ...string) (map[string]any, error) {
	if len(users) == 0 {
		return nil, newError("assign requires at least one user")
	}
	return t.Update(ctx, key, map[string]any{"assignees": users})
}

func (t *Tasks) AssignMe(ctx context.Context, key string, status string) (map[string]any, error) {
	fields := map[string]any{"assignees": []string{"me"}}
	if status != "" {
		fields["status"] = status
	}
	return t.Update(ctx, key, fields)
}

func (t *Tasks) Unassign(ctx context.Context, key string) (map[string]any, error) {
	return t.Update(ctx, key, map[string]any{"clear_assignee": true})
}

func (t *Tasks) Archive(ctx context.Context, key string, cancel bool) (map[string]any, error) {
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/archive",
		withJSON(map[string]any{"cancel": cancel}))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) Restore(ctx context.Context, key string) (map[string]any, error) {
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/restore", withJSON(map[string]any{}))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) Delete(ctx context.Context, key string) error {
	_, err := t.request(ctx, http.MethodDelete, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key))
	return err
}

func (t *Tasks) Activity(ctx context.Context, key string) ([]map[string]any, error) {
	raw, err := t.request(ctx, http.MethodGet, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/activity")
	if err != nil {
		return nil, err
	}
	return itemsOf[map[string]any](raw)
}

func (t *Tasks) Comment(ctx context.Context, key, body string) (map[string]any, error) {
	return t.CommentQuote(ctx, key, body, "")
}

func (t *Tasks) CommentQuote(ctx context.Context, key, body, quoteCommentID string) (map[string]any, error) {
	payload := map[string]any{"body": body}
	if quoteCommentID != "" {
		payload["quote_comment_id"] = quoteCommentID
	}
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/comments",
		withJSON(payload))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) CommentUpdate(ctx context.Context, key, commentID, body string) (map[string]any, error) {
	raw, err := t.request(ctx, http.MethodPatch,
		"accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/comments/"+url.PathEscape(commentID),
		withJSON(map[string]any{"body": body}))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) CommentDelete(ctx context.Context, key, commentID string) (map[string]any, error) {
	raw, err := t.request(ctx, http.MethodDelete,
		"accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/comments/"+url.PathEscape(commentID))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) Watch(ctx context.Context, key, user string) (map[string]any, error) {
	if user == "" {
		user = "me"
	}
	uid, err := t.ResolveUser(ctx, user)
	if err != nil {
		return nil, err
	}
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/watchers",
		withJSON(map[string]any{"user_id": uid}))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) Unwatch(ctx context.Context, key, user string) (map[string]any, error) {
	if user == "" {
		user = "me"
	}
	uid, err := t.ResolveUser(ctx, user)
	if err != nil {
		return nil, err
	}
	raw, err := t.request(ctx, http.MethodDelete,
		"accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/watchers/"+url.PathEscape(uid))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) AddLabel(ctx context.Context, key, name, color string) (map[string]any, error) {
	body := map[string]any{"name": name}
	if color != "" {
		body["color"] = color
	}
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/labels", withJSON(body))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) RemoveLabel(ctx context.Context, key, labelID string) (map[string]any, error) {
	raw, err := t.request(ctx, http.MethodDelete,
		"accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/labels/"+url.PathEscape(labelID))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) Labels(ctx context.Context, includeArchived bool) ([]map[string]any, error) {
	q := url.Values{}
	q.Set("include_archived", "false")
	if includeArchived {
		q.Set("include_archived", "true")
	}
	raw, err := t.request(ctx, http.MethodGet, "accounts/"+t.c.accountID+"/tasks/labels", withQuery(q))
	if err != nil {
		return nil, err
	}
	return itemsOf[map[string]any](raw)
}

func (t *Tasks) CreateLabel(ctx context.Context, name, color string) (map[string]any, error) {
	if color == "" {
		color = "#64748b"
	}
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/labels",
		withJSON(map[string]any{"name": name, "color": color}))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) LinkResource(ctx context.Context, key, resourceType, resourceID, resourceRef string) (map[string]any, error) {
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/resources",
		withJSON(map[string]any{
			"resource_type": resourceType,
			"resource_id":   resourceID,
			"resource_ref":  resourceRef,
		}))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) UnlinkResource(ctx context.Context, key, linkID string) (map[string]any, error) {
	raw, err := t.request(ctx, http.MethodDelete,
		"accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/resources/"+url.PathEscape(linkID))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) CreateShare(ctx context.Context, key, expiresIn, label string, includeDiscussion bool) (map[string]any, error) {
	if expiresIn == "" {
		expiresIn = "never"
	}
	body := map[string]any{"expires_in": expiresIn, "include_discussion": includeDiscussion}
	if label != "" {
		body["label"] = label
	}
	raw, err := t.request(ctx, http.MethodPost, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/shares", withJSON(body))
	if err != nil {
		return nil, err
	}
	return decode[map[string]any](raw)
}

func (t *Tasks) ListShares(ctx context.Context, key string) ([]map[string]any, error) {
	raw, err := t.request(ctx, http.MethodGet, "accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/shares")
	if err != nil {
		return nil, err
	}
	return itemsOf[map[string]any](raw)
}

func (t *Tasks) RevokeShare(ctx context.Context, key, shareID string) error {
	_, err := t.request(ctx, http.MethodDelete,
		"accounts/"+t.c.accountID+"/tasks/items/"+url.PathEscape(key)+"/shares/"+url.PathEscape(shareID))
	return err
}
