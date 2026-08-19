package homecloud

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"strings"
	"time"
)

const (
	HeaderAccessKeyID  = "X-Homecloud-Access-Key-Id"
	HeaderDate         = "X-Homecloud-Date"
	HeaderSignature    = "X-Homecloud-Signature"
	HeaderSessionToken = "X-Homecloud-Session-Token"
	HeaderIdempotency  = "Idempotency-Key"
)

// BuildStringToSign is the SigV1 canonical string:
//
//	{METHOD}\n{path}\n{timestamp}\n{account_id}
func BuildStringToSign(method, path, timestamp, accountID string) string {
	return strings.ToUpper(method) + "\n" + path + "\n" + timestamp + "\n" + accountID
}

func ComputeSignature(secret, stringToSign string) string {
	mac := hmac.New(sha256.New, []byte(secret))
	_, _ = mac.Write([]byte(stringToSign))
	return hex.EncodeToString(mac.Sum(nil))
}

func FormatTimestamp(t time.Time) string {
	return t.UTC().Truncate(time.Second).Format("2006-01-02T15:04:05Z")
}

func signHeaders(accessKeyID, secret, method, path, accountID string, now time.Time, sessionToken string) map[string]string {
	ts := FormatTimestamp(now)
	sig := ComputeSignature(secret, BuildStringToSign(method, path, ts, accountID))
	h := map[string]string{
		HeaderAccessKeyID: accessKeyID,
		HeaderDate:        ts,
		HeaderSignature:   sig,
	}
	if strings.TrimSpace(sessionToken) != "" {
		h[HeaderSessionToken] = sessionToken
	}
	return h
}
