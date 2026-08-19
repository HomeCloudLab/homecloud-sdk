package homecloud

import (
	"encoding/json"
	"time"
)

type Bucket struct {
	ID        string `json:"id,omitempty"`
	Name      string `json:"name"`
	IAMARN    string `json:"iam_arn,omitempty"`
	Status    string `json:"status,omitempty"`
	CreatedAt string `json:"created_at,omitempty"`
}

type ObjectRef struct {
	Key  string `json:"key,omitempty"`
	ETag string `json:"etag,omitempty"`
	Size int64  `json:"size,omitempty"`
}

type DownloadResult struct {
	Key  string `json:"key"`
	Size int64  `json:"size"`
	Path string `json:"path"`
}

type ObjectHead struct {
	Key          string            `json:"key"`
	Size         int64             `json:"size"`
	ETag         string            `json:"etag,omitempty"`
	ContentType  string            `json:"content_type,omitempty"`
	LastModified string            `json:"last_modified,omitempty"`
	Metadata     map[string]string `json:"metadata,omitempty"`
	Tags         map[string]string `json:"tags,omitempty"`
}

type ObjectURI struct {
	SOURI               string `json:"so_uri"`
	HTTPSURL            string `json:"https_url"`
	HTTPSRequiresPublic bool   `json:"https_requires_public"`
}

type PresignedURL struct {
	URL              string `json:"url"`
	ExpiresInSeconds int    `json:"expires_in_seconds"`
}

type ObjectListItem struct {
	Key   string `json:"key"`
	Size  int64  `json:"size"`
	IsDir bool   `json:"is_dir"`
	ETag  string `json:"etag,omitempty"`
}

type ListObjectsResult struct {
	Items                 []ObjectListItem `json:"items"`
	HasMore               bool             `json:"has_more"`
	NextContinuationToken string           `json:"next_continuation_token,omitempty"`
	Pages                 *int             `json:"pages"`
}

type ListObjectsOptions struct {
	Prefix            string
	Recursive         bool
	Page              int
	PageSize          int
	ContinuationToken string
}

type UploadOptions struct {
	FilePath    string
	Body        []byte
	Key         string
	ContentType string
}

type CopyOptions struct {
	SourceBucket string
}

type SyncOptions struct {
	Delete     bool
	Skip       bool
	MaxWorkers int
}

type SyncResult struct {
	Uploaded   int `json:"uploaded,omitempty"`
	Downloaded int `json:"downloaded,omitempty"`
	Copied     int `json:"copied,omitempty"`
	Skipped    int `json:"skipped"`
	Deleted    int `json:"deleted"`
}

type SendOptions struct {
	Headers map[string]string
}

type SendResult struct {
	ID       string `json:"id,omitempty"`
	Sequence int64  `json:"sequence,omitempty"`
	Status   string `json:"status,omitempty"`
}

type ReceiveOptions struct {
	MaxMessages int
	WaitSeconds int
	Delete      bool
}

type Message struct {
	Sequence int64             `json:"sequence"`
	Body     string            `json:"body"`
	Headers  map[string]string `json:"headers,omitempty"`
	ID       string            `json:"id,omitempty"`
}

type Account struct {
	ID   string `json:"id"`
	Slug string `json:"slug,omitempty"`
	Name string `json:"name,omitempty"`
}

type Queue struct {
	ID        string `json:"id,omitempty"`
	Name      string `json:"name"`
	IAMARN    string `json:"iam_arn,omitempty"`
	Status    string `json:"status,omitempty"`
	CreatedAt string `json:"created_at,omitempty"`
}

type Application struct {
	ID     string `json:"id,omitempty"`
	Name   string `json:"name,omitempty"`
	Slug   string `json:"slug,omitempty"`
	Status string `json:"status,omitempty"`
}

type Function struct {
	ID     string `json:"id,omitempty"`
	Name   string `json:"name"`
	Status string `json:"status,omitempty"`
}

type EnableURLOptions struct {
	Public             bool
	RateLimitPerMinute int
}

type Secret struct {
	Name    string          `json:"name,omitempty"`
	Value   json.RawMessage `json:"value,omitempty"`
	Version string          `json:"version,omitempty"`
}

type Mailbox struct {
	ID    string `json:"id"`
	Name  string `json:"name,omitempty"`
	Email string `json:"email,omitempty"`
}

type ListMessagesOptions struct {
	MailboxID string
	Folder    string
	Direction string
	Status    string
	Search    string
	Limit     int
	Cursor    string
}

type MailMessageList struct {
	Items      []MailMessage `json:"items"`
	NextCursor string        `json:"next_cursor,omitempty"`
	HasMore    bool          `json:"has_more"`
}

type MailMessage struct {
	ID        string `json:"id"`
	Subject   string `json:"subject,omitempty"`
	MailboxID string `json:"mailbox_id,omitempty"`
	BodyHTML  string `json:"body_html,omitempty"`
	BodyText  string `json:"body_text,omitempty"`
}

type RegistryRepo struct {
	Name     string `json:"name"`
	KeepLast int    `json:"keep_last,omitempty"`
}

type RegistryList struct {
	Items []RegistryRepo `json:"items"`
}

type LoginBrowserOptions struct {
	OpenBrowser bool
	MFAToken    string
	OnWaiting   func(verificationURI string)
	PollEvery   time.Duration
}

func stringMap(raw any) map[string]string {
	out := map[string]string{}
	m, ok := raw.(map[string]any)
	if !ok {
		return out
	}
	for k, v := range m {
		out[k] = stringify(v)
	}
	return out
}
