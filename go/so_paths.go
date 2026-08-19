package homecloud

import (
	"net/url"
	"strings"
)

func encodeObjectKeyPath(key string) string {
	key = strings.TrimLeft(key, "/")
	parts := strings.Split(key, "/")
	for i, p := range parts {
		parts[i] = url.PathEscape(p)
	}
	return strings.Join(parts, "/")
}

func soObjectPaths(accountID, bucket, objectKey string) (signPath, urlPath string) {
	key := strings.TrimLeft(objectKey, "/")
	signPath = "/" + accountID + "/" + bucket + "/objects/" + key
	urlPath = "/" + accountID + "/" + bucket + "/objects/" + encodeObjectKeyPath(key)
	return signPath, urlPath
}

func isSOURI(target string) bool {
	l := strings.ToLower(strings.TrimSpace(target))
	return strings.HasPrefix(l, "so://") || strings.HasPrefix(l, "s3://")
}

func parseSOURI(target string) (bucket, prefix string, err error) {
	text := strings.TrimSpace(target)
	lower := strings.ToLower(text)
	switch {
	case strings.HasPrefix(lower, "so://"):
		text = text[5:]
	case strings.HasPrefix(lower, "s3://"):
		text = text[5:]
	}
	text = strings.Trim(text, "/")
	if text == "" {
		return "", "", newError("URI must include a bucket name")
	}
	parts := strings.SplitN(text, "/", 2)
	bucket = parts[0]
	if len(parts) > 1 {
		prefix = parts[1]
	}
	return bucket, prefix, nil
}

func syncJoinPrefix(prefixClean, relative string) string {
	rel := strings.TrimLeft(relative, "/")
	if prefixClean == "" {
		return rel
	}
	if rel == "" {
		return prefixClean
	}
	return prefixClean + "/" + rel
}

func syncRelativeLocalPath(key, prefixClean string) string {
	if prefixClean == "" {
		return key
	}
	if key == prefixClean {
		if i := strings.LastIndex(key, "/"); i >= 0 {
			return key[i+1:]
		}
		return key
	}
	if strings.HasPrefix(key, prefixClean+"/") {
		return key[len(prefixClean)+1:]
	}
	return key
}
