package homecloud

import (
	"errors"
	"fmt"
	"net/url"
	"strconv"
	"strings"
)

type base struct {
	Message    string
	StatusCode int
	Detail     any
}

func (b *base) Error() string {
	if b == nil {
		return ""
	}
	return b.Message
}

func (b *base) ErrorPayload() map[string]any {
	if b == nil {
		return nil
	}
	detail, ok := b.Detail.(map[string]any)
	if !ok {
		return nil
	}
	if errObj, ok := detail["error"].(map[string]any); ok {
		if code, _ := errObj["code"].(string); code != "" {
			details, _ := errObj["details"].(map[string]any)
			if details == nil {
				details = map[string]any{}
			}
			msg, _ := errObj["message"].(string)
			if msg == "" {
				msg = code
			}
			return map[string]any{"code": code, "message": msg, "details": details}
		}
	}
	if code, _ := detail["code"].(string); code != "" {
		details := map[string]any{}
		for k, v := range detail {
			if k != "code" && k != "message" {
				details[k] = v
			}
		}
		msg, _ := detail["message"].(string)
		if msg == "" {
			msg = code
		}
		return map[string]any{"code": code, "message": msg, "details": details}
	}
	return nil
}

func (b *base) ErrorCode() string {
	p := b.ErrorPayload()
	if p == nil {
		return ""
	}
	code, _ := p["code"].(string)
	return code
}

// Error is the base HomeCloud SDK error.
type Error struct{ *base }

func (e *Error) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.base
}

func newError(msg string) *Error {
	return &Error{base: &base{Message: msg}}
}

// NotConfiguredError is raised when Access Key / profile is missing.
type NotConfiguredError struct{ *base }

func (e *NotConfiguredError) Unwrap() error { return &Error{e.base} }

// NotLoggedInError is raised when a console JWT is required but missing.
type NotLoggedInError struct{ *base }

func (e *NotLoggedInError) Unwrap() error { return &Error{e.base} }

func newNotLoggedIn() *NotLoggedInError {
	return &NotLoggedInError{base: &base{Message: "This operation needs a console JWT (human session). For automation use Access Key data-plane APIs instead. Interactive: client.Login(...) or homecloud login"}}
}

func newNotConfigured() *NotConfiguredError {
	return &NotConfiguredError{base: &base{Message: "Access Key not configured. Pass access_key_id/secret_access_key, set HOMECLOUD_ACCESS_KEY_ID / HC_ACCESS_KEY_ID, or run: homecloud configure"}}
}

// APIError is an HTTP API error that did not map to a more specific type.
type APIError struct{ *base }

func (e *APIError) Unwrap() error { return &Error{e.base} }

type BadRequestError struct{ *base }

func (e *BadRequestError) Unwrap() error { return &APIError{e.base} }

type UnauthorizedError struct{ *base }

func (e *UnauthorizedError) Unwrap() error { return &APIError{e.base} }

type PermissionDeniedError struct{ *base }

func (e *PermissionDeniedError) Unwrap() error { return &APIError{e.base} }

type NotFoundError struct {
	*base
	ResourceType string
	Resource     string
}

func (e *NotFoundError) Unwrap() error { return &APIError{e.base} }

type ConflictError struct{ *base }

func (e *ConflictError) Unwrap() error { return &APIError{e.base} }

type RateLimitError struct{ *base }

func (e *RateLimitError) Unwrap() error { return &APIError{e.base} }

type ServiceUnavailableError struct{ *base }

func (e *ServiceUnavailableError) Unwrap() error { return &APIError{e.base} }

func IsNotFound(err error) bool {
	var n *NotFoundError
	return errors.As(err, &n)
}

// ErrorFromStatus maps an HTTP failure to a typed error (Python error_from_status).
func ErrorFromStatus(statusCode int, detail any, rawURL string) error {
	apiMsg := detailMessage(detail)
	var resourceType, resource, hintMsg string
	if rawURL != "" {
		resourceType, resource, hintMsg = resourceHint(rawURL)
	}
	b := func(msg string) *base {
		return &base{Message: msg, StatusCode: statusCode, Detail: detail}
	}
	switch statusCode {
	case 400:
		msg := apiMsg
		if msg == "" {
			msg = "Bad request"
		}
		return &BadRequestError{base: b(msg)}
	case 401:
		msg := apiMsg
		if msg == "" {
			msg = "Unauthorized — check Access Key or console session"
		}
		return &UnauthorizedError{base: b(msg)}
	case 403:
		msg := apiMsg
		if msg == "" {
			msg = "Permission denied"
		}
		return &PermissionDeniedError{base: b(msg)}
	case 404:
		message := hintMsg
		if message == "" {
			message = apiMsg
		}
		if message == "" {
			message = "Resource not found"
		}
		if hintMsg != "" && apiMsg != "" && !strings.Contains(hintMsg, apiMsg) {
			message = hintMsg + " (" + apiMsg + ")"
		}
		return &NotFoundError{base: b(message), ResourceType: resourceType, Resource: resource}
	case 409:
		msg := apiMsg
		if msg == "" {
			msg = "Conflict"
		}
		return &ConflictError{base: b(msg)}
	case 429:
		msg := apiMsg
		if msg == "" {
			msg = "Rate limit exceeded"
		}
		return &RateLimitError{base: b(msg)}
	case 502, 503, 504:
		msg := apiMsg
		if msg == "" {
			msg = fmt.Sprintf("Service unavailable (%d)", statusCode)
		}
		return &ServiceUnavailableError{base: b(msg)}
	default:
		msg := apiMsg
		if msg == "" {
			msg = fmt.Sprintf("Request failed (%d)", statusCode)
		}
		return &APIError{base: b(msg)}
	}
}

func detailMessage(detail any) string {
	if detail == nil {
		return ""
	}
	switch d := detail.(type) {
	case string:
		return strings.TrimSpace(d)
	case map[string]any:
		if errObj, ok := d["error"].(map[string]any); ok {
			if msg := stringify(errObj["message"]); msg != "" {
				return msg
			}
			if code := stringify(errObj["code"]); code != "" {
				return code
			}
		}
		if msg := stringify(d["message"]); msg != "" {
			return msg
		}
		if code := stringify(d["code"]); code != "" {
			return code
		}
	case []any:
		parts := make([]string, 0, 3)
		for i, item := range d {
			if i >= 3 {
				break
			}
			if m, ok := item.(map[string]any); ok {
				if msg := stringify(m["msg"]); msg != "" {
					parts = append(parts, msg)
					continue
				}
			}
			parts = append(parts, fmt.Sprint(item))
		}
		return strings.Join(parts, "; ")
	}
	return ""
}

func stringify(v any) string {
	if v == nil {
		return ""
	}
	switch t := v.(type) {
	case string:
		return t
	case float64:
		return strconv.FormatFloat(t, 'f', -1, 64)
	default:
		s := fmt.Sprint(t)
		if s == "<nil>" {
			return ""
		}
		return s
	}
}

func resourceHint(rawURL string) (resourceType, resource, human string) {
	u, err := url.Parse(rawURL)
	if err != nil {
		return "", "", ""
	}
	path, _ := url.PathUnescape(u.Path)
	parts := make([]string, 0)
	for _, p := range strings.Split(path, "/") {
		if p != "" {
			parts = append(parts, p)
		}
	}
	if len(parts) >= 3 {
		name := parts[1]
		kind := parts[2]
		if kind == "objects" {
			keyParts := append([]string{}, parts[3:]...)
			for len(keyParts) > 0 {
				last := keyParts[len(keyParts)-1]
				if last == "metadata" || last == "uri" || last == "presigned" || last == "tags" {
					keyParts = keyParts[:len(keyParts)-1]
					continue
				}
				break
			}
			for i, p := range keyParts {
				if p == "multipart" {
					keyParts = keyParts[:i]
					break
				}
			}
			key := strings.Join(keyParts, "/")
			if key != "" {
				return "object", name + "/" + key, fmt.Sprintf("Object not found: bucket=%q key=%q", name, key)
			}
			return "bucket", name, fmt.Sprintf("Bucket not found: %q", name)
		}
		if kind == "messages" {
			return "queue", name, fmt.Sprintf("Queue not found: %q", name)
		}
	}
	if strings.Contains(path, "storage/buckets") {
		return "bucket", "", "Bucket not found"
	}
	if strings.Contains(path, "/queues") {
		return "queue", "", "Queue not found"
	}
	if strings.Contains(path, "/secrets") {
		return "secret", "", "Secret not found"
	}
	return "", "", ""
}
