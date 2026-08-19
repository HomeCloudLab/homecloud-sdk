package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Object Storage — data plane plus console bucket helpers. */
public final class So {
    private final HomeCloud c;

    So(HomeCloud c) {
        this.c = c;
    }

    public List<Bucket> listBuckets() {
        if (c.hasAccessKey()) {
            c.ensureAccountId();
            byte[] raw = c.dataPlaneJson("so", "GET", "/" + c.accountIdOrEmpty() + "/buckets", "", null, null, null);
            return Json.itemsOf(raw, Bucket.class);
        }
        c.requireConsole();
        c.ensureAccountId();
        byte[] raw = c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/storage/buckets", true, null, null, null, null);
        return Json.itemsOf(raw, Bucket.class);
    }

    public Bucket createBucket(String name) {
        c.ensureAccountId();
        byte[] raw = c.consoleJson(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/storage/buckets",
                true,
                Map.of("name", name.trim().toLowerCase(Locale.ROOT)),
                null,
                Transport.newIdempotencyKey(),
                Transport.RetryMode.IF_IDEMPOTENCY);
        return Json.decode(raw, Bucket.class);
    }

    public void deleteBucket(String name) {
        c.ensureAccountId();
        c.consoleJson(
                "DELETE",
                "accounts/" + c.accountIdOrEmpty() + "/storage/buckets/" + name.trim().toLowerCase(Locale.ROOT),
                true, null, null, null, null);
    }

    public ListObjectsResult listObjects(String bucket, ListObjectsOptions opts) {
        c.requireAccessKey();
        c.ensureAccountId();
        if (opts == null) {
            opts = ListObjectsOptions.builder().build();
        }
        int page = opts.page() <= 0 ? 1 : opts.page();
        int pageSize = opts.pageSize() <= 0 ? 100 : opts.pageSize();
        Map<String, String> q = new LinkedHashMap<>();
        q.put("prefix", opts.prefix());
        q.put("recursive", opts.recursive() ? "true" : "false");
        q.put("page", Integer.toString(page));
        q.put("page_size", Integer.toString(pageSize));
        if (!opts.continuationToken().isEmpty()) {
            q.put("continuation_token", opts.continuationToken());
        }
        String path = "/" + c.accountIdOrEmpty() + "/" + bucket + "/objects";
        byte[] raw = c.dataPlaneJson("so", "GET", path, "", q, null, null);
        ListObjectsResult res = Json.decode(raw, ListObjectsResult.class);
        return res == null ? new ListObjectsResult(List.of(), false, "", null) : res;
    }

    public List<ObjectListItem> listAllObjects(String bucket, ListObjectsOptions opts) {
        if (opts == null) {
            opts = ListObjectsOptions.builder().build();
        }
        List<ObjectListItem> items = new ArrayList<>();
        int page = 1;
        String token = "";
        boolean recursive = true;
        if (opts.page() > 0 || opts.pageSize() > 0) {
            recursive = opts.recursive();
        }
        while (true) {
            ListObjectsResult data = listObjects(bucket, ListObjectsOptions.builder()
                    .prefix(opts.prefix())
                    .recursive(recursive)
                    .page(page)
                    .pageSize(100)
                    .continuationToken(token)
                    .build());
            for (ObjectListItem item : data.items()) {
                if (!item.isDir()) {
                    items.add(item);
                }
            }
            if (data.hasMore() && data.nextContinuationToken() != null && !data.nextContinuationToken().isEmpty()) {
                token = data.nextContinuationToken();
                page = 1;
                continue;
            }
            if (data.pages() != null && page < data.pages()) {
                page++;
                token = "";
                continue;
            }
            break;
        }
        return items;
    }

    public ObjectRef upload(String bucket, UploadOptions opts) {
        c.requireAccessKey();
        c.ensureAccountId();
        if (opts.body() != null && opts.filePath() != null && !opts.filePath().isEmpty()) {
            throw new HomeCloudException("Pass either filePath or body, not both");
        }
        if (opts.body() == null && (opts.filePath() == null || opts.filePath().isEmpty())) {
            throw new HomeCloudException("filePath or body is required");
        }
        if (opts.body() != null && (opts.key() == null || opts.key().isBlank())) {
            throw new HomeCloudException("key is required when uploading body");
        }
        Transport.Spec spec = new Transport.Spec();
        spec.method = "POST";
        spec.accountId = c.accountIdOrEmpty();
        spec.signed = true;
        spec.retry = Transport.RetryMode.UPLOAD;
        String objectKey;
        String filename;
        if (opts.body() != null) {
            objectKey = SoPaths.trimLeftSlash(opts.key().trim());
            filename = Path.of(objectKey).getFileName() == null ? "object" : Path.of(objectKey).getFileName().toString();
            if (filename.isEmpty() || ".".equals(filename)) {
                filename = "object";
            }
            spec.multipartBytes = opts.body();
        } else {
            Path p = Path.of(opts.filePath());
            if (!Files.isRegularFile(p)) {
                throw new HomeCloudException("File not found: " + opts.filePath());
            }
            objectKey = opts.key() == null || opts.key().isBlank() ? p.getFileName().toString() : opts.key();
            filename = p.getFileName().toString();
            spec.multipartFile = opts.filePath();
        }
        spec.multipartKey = objectKey;
        spec.multipartName = filename;
        spec.signPath = "/" + c.accountIdOrEmpty() + "/" + bucket + "/objects";
        spec.url = c.dataPlaneBase("so") + spec.signPath;
        byte[] raw = Transport.doRequest(c, spec);
        ObjectRef ref = Json.decode(raw, ObjectRef.class);
        if (ref == null || ref.key() == null || ref.key().isEmpty()) {
            return new ObjectRef(objectKey, ref == null ? "" : ref.etag(), ref == null ? 0 : ref.size());
        }
        return ref;
    }

    public ObjectRef putJson(String bucket, String key, Object value) {
        try {
            byte[] raw = Json.MAPPER.writerWithDefaultPrettyPrinter().writeValueAsBytes(value);
            return upload(bucket, UploadOptions.builder().key(key).body(raw).contentType("application/json").build());
        } catch (HomeCloudException e) {
            throw e;
        } catch (Exception e) {
            throw new HomeCloudException("Invalid JSON", e);
        }
    }

    public void delete(String bucket, String objectKey) {
        c.ensureAccountId();
        String[] paths = SoPaths.soObjectPaths(c.accountIdOrEmpty(), bucket, objectKey);
        c.dataPlaneJson("so", "DELETE", paths[0], paths[1], null, null, null);
    }

    public JsonNode copy(String bucket, String sourceKey, String destinationKey, CopyOptions opts) {
        c.ensureAccountId();
        String[] paths = SoPaths.soObjectPaths(c.accountIdOrEmpty(), bucket, sourceKey);
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("destination_key", destinationKey);
        body.put("source_bucket", opts != null && opts.sourceBucket() != null && !opts.sourceBucket().isEmpty()
                ? opts.sourceBucket() : null);
        return Json.parse(c.dataPlaneJson("so", "POST", paths[0] + "/copy", paths[1] + "/copy", null, body, Transport.RetryMode.UPLOAD));
    }

    public JsonNode move(String bucket, String sourceKey, String destinationKey, CopyOptions opts) {
        JsonNode copied = copy(bucket, sourceKey, destinationKey, opts);
        headObject(bucket, destinationKey);
        String srcBucket = opts != null && opts.sourceBucket() != null && !opts.sourceBucket().isEmpty()
                ? opts.sourceBucket() : bucket;
        delete(srcBucket, sourceKey);
        return copied;
    }

    public DownloadResult download(String bucket, String objectKey, String destPath) {
        c.requireAccessKey();
        c.ensureAccountId();
        String key = SoPaths.trimLeftSlash(objectKey);
        String[] paths = SoPaths.soObjectPaths(c.accountIdOrEmpty(), bucket, key);
        try {
            Path dest = Path.of(destPath);
            if (dest.getParent() != null) {
                Files.createDirectories(dest.getParent());
            }
            Transport.Spec spec = new Transport.Spec();
            spec.method = "GET";
            spec.url = c.dataPlaneBase("so") + paths[1];
            spec.signPath = paths[0];
            spec.accountId = c.accountIdOrEmpty();
            spec.signed = true;
            spec.retry = Transport.RetryMode.IDEMPOTENT;
            spec.stream = true;
            byte[] raw = Transport.doRequest(c, spec);
            Files.write(dest, raw);
            return new DownloadResult(key, raw.length, destPath);
        } catch (HomeCloudException e) {
            throw e;
        } catch (Exception e) {
            throw new HomeCloudException("Download failed", e);
        }
    }

    public ObjectHead headObject(String bucket, String objectKey) {
        c.ensureAccountId();
        String key = SoPaths.trimLeftSlash(objectKey);
        String[] paths = SoPaths.soObjectPaths(c.accountIdOrEmpty(), bucket, key);
        byte[] raw = c.dataPlaneJson("so", "GET", paths[0] + "/metadata", paths[1] + "/metadata", null, null, null);
        JsonNode parsed = Json.parse(raw);
        Map<String, Object> map = Json.asMap(parsed);
        String k = Errors.stringify(map.get("key"));
        ObjectHead head = new ObjectHead(
                k.isEmpty() ? key : k,
                jsonLong(map.get("size")),
                Errors.stringify(map.get("etag")),
                Errors.stringify(map.get("content_type")),
                Errors.stringify(map.get("last_modified")),
                Json.stringMap(map.get("metadata")),
                Json.stringMap(map.get("tags")));
        return head;
    }

    public ObjectUri getObjectUri(String bucket, String objectKey) {
        c.ensureAccountId();
        String key = SoPaths.trimLeftSlash(objectKey);
        String[] paths = SoPaths.soObjectPaths(c.accountIdOrEmpty(), bucket, key);
        byte[] raw = c.dataPlaneJson("so", "GET", paths[0] + "/uri", paths[1] + "/uri", null, null, null);
        ObjectUri u = Json.decode(raw, ObjectUri.class);
        if (u == null || u.soUri() == null || u.soUri().isEmpty()) {
            return new ObjectUri("so://" + bucket + "/" + key, u == null ? "" : u.httpsUrl(), u != null && u.httpsRequiresPublic());
        }
        return u;
    }

    public PresignedUrl generatePresignedUrl(String bucket, String objectKey, int expires) {
        if (expires <= 0) {
            expires = 3600;
        }
        c.ensureAccountId();
        String key = SoPaths.trimLeftSlash(objectKey);
        String[] paths = SoPaths.soObjectPaths(c.accountIdOrEmpty(), bucket, key);
        Map<String, String> q = Map.of("expires", Integer.toString(expires));
        byte[] raw = c.dataPlaneJson("so", "GET", paths[0] + "/presigned", paths[1] + "/presigned", q, null, null);
        PresignedUrl u = Json.decode(raw, PresignedUrl.class);
        if (u == null || u.url() == null || u.url().isEmpty()) {
            throw new HomeCloudException("Invalid presigned URL response");
        }
        if (u.expiresInSeconds() == 0) {
            return new PresignedUrl(u.url(), expires);
        }
        return u;
    }

    public int deleteRecursive(String bucket, String prefix) {
        List<ObjectListItem> items = listAllObjects(bucket, ListObjectsOptions.builder().prefix(prefix).recursive(true).build());
        for (ObjectListItem item : items) {
            delete(bucket, item.key());
        }
        return items.size();
    }

    public SyncResult sync(String source, String destination, SyncOptions opts) {
        if (opts == null) {
            opts = SyncOptions.none();
        }
        boolean srcRemote = SoPaths.isSoUri(source);
        boolean dstRemote = SoPaths.isSoUri(destination);
        if (srcRemote && dstRemote) {
            String[] s = SoPaths.parseSoUri(source);
            String[] d = SoPaths.parseSoUri(destination);
            return syncBucketToBucket(s[0], d[0], s[1], d[1], opts);
        }
        if (srcRemote) {
            String[] s = SoPaths.parseSoUri(source);
            return syncBucketToLocal(s[0], destination, s[1], opts);
        }
        if (dstRemote) {
            String[] d = SoPaths.parseSoUri(destination);
            return syncLocalToBucket(source, d[0], d[1], opts);
        }
        throw new HomeCloudException("One or both sides must be an so:// URI. Examples: ./dir so://bucket/  |  so://bucket/ ./dir  |  so://a/ so://b/");
    }

    private SyncResult syncLocalToBucket(String localDir, String bucket, String prefix, SyncOptions opts) {
        Path dir = Path.of(localDir);
        if (!Files.isDirectory(dir)) {
            throw new HomeCloudException("Not a directory: " + localDir);
        }
        String prefixClean = trimSlash(prefix);
        Map<String, Path> localFiles = new LinkedHashMap<>();
        try (var walk = Files.walk(dir)) {
            walk.filter(Files::isRegularFile).forEach(path -> {
                String rel = dir.relativize(path).toString().replace('\\', '/');
                localFiles.put(SoPaths.syncJoinPrefix(prefixClean, rel), path);
            });
        } catch (Exception e) {
            throw new HomeCloudException("Failed to walk directory", e);
        }
        Map<String, ObjectListItem> remoteByKey = new LinkedHashMap<>();
        for (ObjectListItem it : listAllObjects(bucket, ListObjectsOptions.builder().prefix(prefixClean).recursive(true).build())) {
            remoteByKey.put(it.key(), it);
        }
        int uploaded = 0, skipped = 0, deleted = 0;
        for (var e : localFiles.entrySet()) {
            try {
                long size = Files.size(e.getValue());
                if (opts.skip()) {
                    ObjectListItem r = remoteByKey.get(e.getKey());
                    if (r != null && r.size() == size) {
                        skipped++;
                        continue;
                    }
                }
                upload(bucket, UploadOptions.builder().filePath(e.getValue().toString()).key(e.getKey()).build());
                uploaded++;
            } catch (HomeCloudException ex) {
                throw ex;
            } catch (Exception ex) {
                throw new HomeCloudException("Sync upload failed", ex);
            }
        }
        if (opts.delete()) {
            for (String key : remoteByKey.keySet()) {
                if (!localFiles.containsKey(key)) {
                    delete(bucket, key);
                    deleted++;
                }
            }
        }
        return new SyncResult(uploaded, 0, 0, skipped, deleted);
    }

    private SyncResult syncBucketToLocal(String bucket, String localDir, String prefix, SyncOptions opts) {
        try {
            Files.createDirectories(Path.of(localDir));
        } catch (Exception e) {
            throw new HomeCloudException("Failed to create directory", e);
        }
        String prefixClean = trimSlash(prefix);
        int downloaded = 0, skipped = 0, deleted = 0;
        Map<String, ObjectListItem> remoteKeys = new LinkedHashMap<>();
        for (ObjectListItem it : listAllObjects(bucket, ListObjectsOptions.builder().prefix(prefixClean).recursive(true).build())) {
            remoteKeys.put(it.key(), it);
            String rel = SoPaths.syncRelativeLocalPath(it.key(), prefixClean);
            Path dest = Path.of(localDir, rel.replace('/', java.io.File.separatorChar));
            if (opts.skip() && Files.isRegularFile(dest)) {
                try {
                    if (Files.size(dest) == it.size()) {
                        skipped++;
                        continue;
                    }
                } catch (Exception ignored) {
                    // download
                }
            }
            download(bucket, it.key(), dest.toString());
            downloaded++;
        }
        if (opts.delete()) {
            Path root = Path.of(localDir);
            try (var walk = Files.walk(root)) {
                for (Path path : walk.filter(Files::isRegularFile).toList()) {
                    String rel = root.relativize(path).toString().replace('\\', '/');
                    String key = SoPaths.syncJoinPrefix(prefixClean, rel);
                    if (!remoteKeys.containsKey(key)) {
                        Files.deleteIfExists(path);
                        deleted++;
                    }
                }
            } catch (Exception e) {
                throw new HomeCloudException("Sync delete failed", e);
            }
        }
        return new SyncResult(0, downloaded, 0, skipped, deleted);
    }

    private SyncResult syncBucketToBucket(String srcBucket, String dstBucket, String srcPrefix, String dstPrefix, SyncOptions opts) {
        srcPrefix = trimSlash(srcPrefix);
        dstPrefix = trimSlash(dstPrefix);
        Map<String, ObjectListItem> destByRel = new LinkedHashMap<>();
        for (ObjectListItem it : listAllObjects(dstBucket, ListObjectsOptions.builder().prefix(dstPrefix).recursive(true).build())) {
            destByRel.put(SoPaths.syncRelativeLocalPath(it.key(), dstPrefix), it);
        }
        int copied = 0, skipped = 0, deleted = 0;
        Map<String, ObjectListItem> srcRels = new LinkedHashMap<>();
        for (ObjectListItem it : listAllObjects(srcBucket, ListObjectsOptions.builder().prefix(srcPrefix).recursive(true).build())) {
            String rel = SoPaths.syncRelativeLocalPath(it.key(), srcPrefix);
            srcRels.put(rel, it);
            if (opts.skip()) {
                ObjectListItem d = destByRel.get(rel);
                if (d != null && d.size() == it.size()) {
                    skipped++;
                    continue;
                }
            }
            String dstKey = SoPaths.syncJoinPrefix(dstPrefix, rel);
            CopyOptions copyOpts = srcBucket.equals(dstBucket) ? CopyOptions.none() : new CopyOptions(srcBucket);
            copy(dstBucket, it.key(), dstKey, copyOpts);
            copied++;
        }
        if (opts.delete()) {
            for (var e : destByRel.entrySet()) {
                if (!srcRels.containsKey(e.getKey())) {
                    delete(dstBucket, e.getValue().key());
                    deleted++;
                }
            }
        }
        return new SyncResult(0, 0, copied, skipped, deleted);
    }

    private static String trimSlash(String s) {
        if (s == null) {
            return "";
        }
        int a = 0, b = s.length();
        while (a < b && s.charAt(a) == '/') a++;
        while (b > a && s.charAt(b - 1) == '/') b--;
        return s.substring(a, b);
    }

    private static long jsonLong(Object v) {
        if (v instanceof Number n) {
            return n.longValue();
        }
        if (v == null) {
            return 0;
        }
        try {
            return Long.parseLong(String.valueOf(v));
        } catch (NumberFormatException e) {
            return 0;
        }
    }
}
