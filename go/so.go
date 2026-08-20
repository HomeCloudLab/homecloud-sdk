package homecloud

import (
	"context"
	"encoding/json"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// SO is Object Storage (data plane + console bucket helpers).
type SO struct{ c *Client }

func (s *SO) ListBuckets(ctx context.Context) ([]Bucket, error) {
	if s.c.hasAccessKey() {
		if err := s.c.ensureAccountID(ctx); err != nil {
			return nil, err
		}
		raw, err := s.c.dataPlaneJSON(ctx, "so", http.MethodGet, "/"+s.c.accountID+"/buckets", s.c.accountID)
		if err != nil {
			return nil, err
		}
		return itemsOf[Bucket](raw)
	}
	if err := s.c.requireConsole(); err != nil {
		return nil, err
	}
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	raw, err := s.c.consoleJSON(ctx, http.MethodGet, "accounts/"+s.c.accountID+"/storage/buckets", true)
	if err != nil {
		return nil, err
	}
	return itemsOf[Bucket](raw)
}

func (s *SO) CreateBucket(ctx context.Context, name string) (*Bucket, error) {
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	path := "accounts/" + s.c.accountID + "/storage/buckets"
	body := map[string]string{"name": strings.ToLower(strings.TrimSpace(name))}
	opts := []func(*requestSpec){withJSON(body), withIdempotency(newIdempotencyKey())}
	var (
		raw json.RawMessage
		err error
	)
	if s.c.hasAccessKey() {
		raw, err = s.c.consoleSignedJSON(ctx, http.MethodPost, path, s.c.accountID, opts...)
	} else {
		raw, err = s.c.consoleJSON(ctx, http.MethodPost, path, true, opts...)
	}
	if err != nil {
		return nil, err
	}
	b, err := decode[Bucket](raw)
	if err != nil {
		return nil, err
	}
	return &b, nil
}

func (s *SO) DeleteBucket(ctx context.Context, name string) error {
	if err := s.c.ensureAccountID(ctx); err != nil {
		return err
	}
	path := "accounts/" + s.c.accountID + "/storage/buckets/" + strings.ToLower(strings.TrimSpace(name))
	if s.c.hasAccessKey() {
		_, err := s.c.consoleSignedJSON(ctx, http.MethodDelete, path, s.c.accountID)
		return err
	}
	_, err := s.c.consoleJSON(ctx, http.MethodDelete, path, true)
	return err
}

func (s *SO) ListObjects(ctx context.Context, bucket string, opts ListObjectsOptions) (*ListObjectsResult, error) {
	if err := s.c.requireAccessKey(); err != nil {
		return nil, err
	}
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if opts.Page <= 0 {
		opts.Page = 1
	}
	if opts.PageSize <= 0 {
		opts.PageSize = 100
	}
	q := url.Values{}
	q.Set("prefix", opts.Prefix)
	if opts.Recursive {
		q.Set("recursive", "true")
	} else {
		q.Set("recursive", "false")
	}
	q.Set("page", itoa(opts.Page))
	q.Set("page_size", itoa(opts.PageSize))
	if opts.ContinuationToken != "" {
		q.Set("continuation_token", opts.ContinuationToken)
	}
	path := "/" + s.c.accountID + "/" + bucket + "/objects"
	raw, err := s.c.dataPlaneJSON(ctx, "so", http.MethodGet, path, s.c.accountID, withQuery(q))
	if err != nil {
		return nil, err
	}
	res, err := decode[ListObjectsResult](raw)
	if err != nil {
		return nil, err
	}
	return &res, nil
}

func (s *SO) ListAllObjects(ctx context.Context, bucket string, opts ListObjectsOptions) ([]ObjectListItem, error) {
	items := []ObjectListItem{}
	page := 1
	token := ""
	recursive := true
	if opts.Page > 0 || opts.PageSize > 0 {
		recursive = opts.Recursive
	}
	for {
		data, err := s.ListObjects(ctx, bucket, ListObjectsOptions{
			Prefix:            opts.Prefix,
			Recursive:         recursive,
			Page:              page,
			PageSize:          100,
			ContinuationToken: token,
		})
		if err != nil {
			return nil, err
		}
		for _, item := range data.Items {
			if item.IsDir {
				continue
			}
			items = append(items, item)
		}
		if data.HasMore && data.NextContinuationToken != "" {
			token = data.NextContinuationToken
			page = 1
			continue
		}
		if data.Pages != nil && page < *data.Pages {
			page++
			token = ""
			continue
		}
		break
	}
	return items, nil
}

func (s *SO) Upload(ctx context.Context, bucket string, opts UploadOptions) (*ObjectRef, error) {
	if err := s.c.requireAccessKey(); err != nil {
		return nil, err
	}
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	if opts.Body != nil && opts.FilePath != "" {
		return nil, newError("Pass either file_path or body, not both")
	}
	if opts.Body == nil && opts.FilePath == "" {
		return nil, newError("file_path or body is required")
	}
	if opts.Body != nil && strings.TrimSpace(opts.Key) == "" {
		return nil, newError("key is required when uploading body")
	}
	var objectKey, filename, mime string
	spec := requestSpec{
		method:    http.MethodPost,
		accountID: s.c.accountID,
		signed:    true,
		retry:     retryUpload,
	}
	if opts.Body != nil {
		objectKey = strings.TrimLeft(strings.TrimSpace(opts.Key), "/")
		filename = filepath.Base(objectKey)
		if filename == "" || filename == "." {
			filename = "object"
		}
		spec.multipartBytes = opts.Body
	} else {
		info, err := os.Stat(opts.FilePath)
		if err != nil || info.IsDir() {
			return nil, newError("File not found: " + opts.FilePath)
		}
		objectKey = opts.Key
		if objectKey == "" {
			objectKey = filepath.Base(opts.FilePath)
		}
		filename = filepath.Base(opts.FilePath)
		spec.multipartFile = opts.FilePath
	}
	mime = opts.ContentType
	if mime == "" {
		mime = guessContentType(objectKey)
		if mime == "application/octet-stream" {
			mime = guessContentType(filename)
		}
	}
	_ = mime // stored by multipart file header via CreateFormFile; MIME is filename-based
	spec.multipartKey = objectKey
	spec.multipartName = filename
	spec.multipartMIME = mime
	spec.signPath = "/" + s.c.accountID + "/" + bucket + "/objects"
	spec.url = s.c.dataPlaneBase("so") + spec.signPath
	raw, err := s.c.doJSON(ctx, spec)
	if err != nil {
		return nil, err
	}
	ref, err := decode[ObjectRef](raw)
	if err != nil {
		return nil, err
	}
	if ref.Key == "" {
		ref.Key = objectKey
	}
	return &ref, nil
}

func (s *SO) PutJSON(ctx context.Context, bucket, key string, value any) (*ObjectRef, error) {
	raw, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return nil, err
	}
	return s.Upload(ctx, bucket, UploadOptions{Key: key, Body: raw, ContentType: "application/json"})
}

func (s *SO) Delete(ctx context.Context, bucket, objectKey string) error {
	if err := s.c.ensureAccountID(ctx); err != nil {
		return err
	}
	signPath, urlPath := soObjectPaths(s.c.accountID, bucket, objectKey)
	_, err := s.c.dataPlaneJSON(ctx, "so", http.MethodDelete, signPath, s.c.accountID, withURLPath(urlPath))
	return err
}

func (s *SO) Copy(ctx context.Context, bucket, sourceKey, destinationKey string, opts CopyOptions) (json.RawMessage, error) {
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	signPath, urlPath := soObjectPaths(s.c.accountID, bucket, sourceKey)
	body := map[string]any{"destination_key": destinationKey, "source_bucket": nil}
	if opts.SourceBucket != "" {
		body["source_bucket"] = opts.SourceBucket
	}
	return s.c.dataPlaneJSON(ctx, "so", http.MethodPost, signPath+"/copy", s.c.accountID,
		withURLPath(urlPath+"/copy"), withJSON(body), withRetry(retryUpload))
}

func (s *SO) Move(ctx context.Context, bucket, sourceKey, destinationKey string, opts CopyOptions) (json.RawMessage, error) {
	copied, err := s.Copy(ctx, bucket, sourceKey, destinationKey, opts)
	if err != nil {
		return nil, err
	}
	if _, err := s.HeadObject(ctx, bucket, destinationKey); err != nil {
		return nil, err
	}
	srcBucket := bucket
	if opts.SourceBucket != "" {
		srcBucket = opts.SourceBucket
	}
	if err := s.Delete(ctx, srcBucket, sourceKey); err != nil {
		return nil, err
	}
	return copied, nil
}

func (s *SO) Download(ctx context.Context, bucket, objectKey, destPath string) (*DownloadResult, error) {
	if err := s.c.requireAccessKey(); err != nil {
		return nil, err
	}
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	key := strings.TrimLeft(objectKey, "/")
	signPath, urlPath := soObjectPaths(s.c.accountID, bucket, key)
	if err := os.MkdirAll(filepath.Dir(destPath), 0o755); err != nil {
		return nil, err
	}
	spec := requestSpec{
		method:    http.MethodGet,
		url:       s.c.dataPlaneBase("so") + urlPath,
		signPath:  signPath,
		accountID: s.c.accountID,
		signed:    true,
		retry:     retryIdempotent,
		stream:    true,
	}
	raw, err := s.c.do(ctx, spec)
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(destPath, raw, 0o644); err != nil {
		return nil, err
	}
	return &DownloadResult{Key: key, Size: int64(len(raw)), Path: destPath}, nil
}

func (s *SO) HeadObject(ctx context.Context, bucket, objectKey string) (*ObjectHead, error) {
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	key := strings.TrimLeft(objectKey, "/")
	signPath, urlPath := soObjectPaths(s.c.accountID, bucket, key)
	raw, err := s.c.dataPlaneJSON(ctx, "so", http.MethodGet, signPath+"/metadata", s.c.accountID, withURLPath(urlPath+"/metadata"))
	if err != nil {
		return nil, err
	}
	var parsed map[string]any
	if err := json.Unmarshal(raw, &parsed); err != nil {
		return nil, newError("Invalid metadata response")
	}
	head := &ObjectHead{
		Key:          stringify(parsed["key"]),
		Size:         jsonInt64(parsed["size"]),
		ETag:         stringify(parsed["etag"]),
		ContentType:  stringify(parsed["content_type"]),
		LastModified: stringify(parsed["last_modified"]),
		Metadata:     stringMap(parsed["metadata"]),
		Tags:         stringMap(parsed["tags"]),
	}
	if head.Key == "" {
		head.Key = key
	}
	return head, nil
}

func (s *SO) GetObjectURI(ctx context.Context, bucket, objectKey string) (*ObjectURI, error) {
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	key := strings.TrimLeft(objectKey, "/")
	signPath, urlPath := soObjectPaths(s.c.accountID, bucket, key)
	raw, err := s.c.dataPlaneJSON(ctx, "so", http.MethodGet, signPath+"/uri", s.c.accountID, withURLPath(urlPath+"/uri"))
	if err != nil {
		return nil, err
	}
	u, err := decode[ObjectURI](raw)
	if err != nil {
		return nil, newError("Invalid URI response")
	}
	if u.SOURI == "" {
		u.SOURI = "so://" + bucket + "/" + key
	}
	return &u, nil
}

func (s *SO) GeneratePresignedURL(ctx context.Context, bucket, objectKey string, expires int) (*PresignedURL, error) {
	if expires <= 0 {
		expires = 3600
	}
	if err := s.c.ensureAccountID(ctx); err != nil {
		return nil, err
	}
	key := strings.TrimLeft(objectKey, "/")
	signPath, urlPath := soObjectPaths(s.c.accountID, bucket, key)
	q := url.Values{}
	q.Set("expires", itoa(expires))
	raw, err := s.c.dataPlaneJSON(ctx, "so", http.MethodGet, signPath+"/presigned", s.c.accountID,
		withURLPath(urlPath+"/presigned"), withQuery(q))
	if err != nil {
		return nil, err
	}
	u, err := decode[PresignedURL](raw)
	if err != nil || u.URL == "" {
		return nil, newError("Invalid presigned URL response")
	}
	if u.ExpiresInSeconds == 0 {
		u.ExpiresInSeconds = expires
	}
	return &u, nil
}

func (s *SO) DeleteRecursive(ctx context.Context, bucket, prefix string) (int, error) {
	items, err := s.ListAllObjects(ctx, bucket, ListObjectsOptions{Prefix: prefix, Recursive: true})
	if err != nil {
		return 0, err
	}
	for _, item := range items {
		if err := s.Delete(ctx, bucket, item.Key); err != nil {
			return 0, err
		}
	}
	return len(items), nil
}

func (s *SO) Sync(ctx context.Context, source, destination string, opts SyncOptions) (*SyncResult, error) {
	srcRemote := isSOURI(source)
	dstRemote := isSOURI(destination)
	switch {
	case srcRemote && dstRemote:
		sb, sp, err := parseSOURI(source)
		if err != nil {
			return nil, err
		}
		db, dp, err := parseSOURI(destination)
		if err != nil {
			return nil, err
		}
		return s.syncBucketToBucket(ctx, sb, db, sp, dp, opts)
	case srcRemote && !dstRemote:
		b, p, err := parseSOURI(source)
		if err != nil {
			return nil, err
		}
		return s.syncBucketToLocal(ctx, b, destination, p, opts)
	case !srcRemote && dstRemote:
		b, p, err := parseSOURI(destination)
		if err != nil {
			return nil, err
		}
		return s.syncLocalToBucket(ctx, source, b, p, opts)
	default:
		return nil, newError("One or both sides must be an so:// URI. Examples: ./dir so://bucket/  |  so://bucket/ ./dir  |  so://a/ so://b/")
	}
}

func (s *SO) syncLocalToBucket(ctx context.Context, localDir, bucket, prefix string, opts SyncOptions) (*SyncResult, error) {
	info, err := os.Stat(localDir)
	if err != nil || !info.IsDir() {
		return nil, newError("Not a directory: " + localDir)
	}
	prefixClean := strings.Trim(prefix, "/")
	localFiles := map[string]string{}
	_ = filepath.Walk(localDir, func(path string, fi os.FileInfo, err error) error {
		if err != nil || fi.IsDir() {
			return nil
		}
		rel, _ := filepath.Rel(localDir, path)
		rel = filepath.ToSlash(rel)
		localFiles[syncJoinPrefix(prefixClean, rel)] = path
		return nil
	})
	remote, err := s.ListAllObjects(ctx, bucket, ListObjectsOptions{Prefix: prefixClean, Recursive: true})
	if err != nil {
		return nil, err
	}
	remoteByKey := map[string]ObjectListItem{}
	for _, it := range remote {
		remoteByKey[it.Key] = it
	}
	res := &SyncResult{}
	for key, path := range localFiles {
		st, _ := os.Stat(path)
		if opts.Skip {
			if r, ok := remoteByKey[key]; ok && r.Size == st.Size() {
				res.Skipped++
				continue
			}
		}
		if _, err := s.Upload(ctx, bucket, UploadOptions{FilePath: path, Key: key}); err != nil {
			return nil, err
		}
		res.Uploaded++
	}
	if opts.Delete {
		for key := range remoteByKey {
			if _, ok := localFiles[key]; !ok {
				if err := s.Delete(ctx, bucket, key); err != nil {
					return nil, err
				}
				res.Deleted++
			}
		}
	}
	return res, nil
}

func (s *SO) syncBucketToLocal(ctx context.Context, bucket, localDir, prefix string, opts SyncOptions) (*SyncResult, error) {
	if err := os.MkdirAll(localDir, 0o755); err != nil {
		return nil, err
	}
	prefixClean := strings.Trim(prefix, "/")
	remote, err := s.ListAllObjects(ctx, bucket, ListObjectsOptions{Prefix: prefixClean, Recursive: true})
	if err != nil {
		return nil, err
	}
	res := &SyncResult{}
	remoteKeys := map[string]ObjectListItem{}
	for _, it := range remote {
		remoteKeys[it.Key] = it
		rel := syncRelativeLocalPath(it.Key, prefixClean)
		dest := filepath.Join(localDir, filepath.FromSlash(rel))
		if opts.Skip {
			if st, err := os.Stat(dest); err == nil && st.Size() == it.Size {
				res.Skipped++
				continue
			}
		}
		if _, err := s.Download(ctx, bucket, it.Key, dest); err != nil {
			return nil, err
		}
		res.Downloaded++
	}
	if opts.Delete {
		_ = filepath.Walk(localDir, func(path string, fi os.FileInfo, err error) error {
			if err != nil || fi.IsDir() {
				return nil
			}
			rel, _ := filepath.Rel(localDir, path)
			key := syncJoinPrefix(prefixClean, filepath.ToSlash(rel))
			if _, ok := remoteKeys[key]; !ok {
				_ = os.Remove(path)
				res.Deleted++
			}
			return nil
		})
	}
	return res, nil
}

func (s *SO) syncBucketToBucket(ctx context.Context, srcBucket, dstBucket, srcPrefix, dstPrefix string, opts SyncOptions) (*SyncResult, error) {
	srcPrefix = strings.Trim(srcPrefix, "/")
	dstPrefix = strings.Trim(dstPrefix, "/")
	remote, err := s.ListAllObjects(ctx, srcBucket, ListObjectsOptions{Prefix: srcPrefix, Recursive: true})
	if err != nil {
		return nil, err
	}
	dest, err := s.ListAllObjects(ctx, dstBucket, ListObjectsOptions{Prefix: dstPrefix, Recursive: true})
	if err != nil {
		return nil, err
	}
	destByRel := map[string]ObjectListItem{}
	for _, it := range dest {
		rel := syncRelativeLocalPath(it.Key, dstPrefix)
		destByRel[rel] = it
	}
	res := &SyncResult{}
	srcRels := map[string]ObjectListItem{}
	for _, it := range remote {
		rel := syncRelativeLocalPath(it.Key, srcPrefix)
		srcRels[rel] = it
		if opts.Skip {
			if d, ok := destByRel[rel]; ok && d.Size == it.Size {
				res.Skipped++
				continue
			}
		}
		dstKey := syncJoinPrefix(dstPrefix, rel)
		copyOpts := CopyOptions{}
		if srcBucket != dstBucket {
			copyOpts.SourceBucket = srcBucket
		}
		if _, err := s.Copy(ctx, dstBucket, it.Key, dstKey, copyOpts); err != nil {
			return nil, err
		}
		res.Copied++
	}
	if opts.Delete {
		for rel, it := range destByRel {
			if _, ok := srcRels[rel]; !ok {
				if err := s.Delete(ctx, dstBucket, it.Key); err != nil {
					return nil, err
				}
				res.Deleted++
			}
		}
	}
	return res, nil
}

func itoa(n int) string {
	return strconv.Itoa(n)
}
