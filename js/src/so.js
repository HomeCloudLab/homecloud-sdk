"use strict";

const fs = require("fs");
const path = require("path");
const { soObjectPaths } = require("./signing");
const { HomeCloudError } = require("./errors");

const MIME_BY_EXT = {
  ".mp4": "video/mp4",
  ".webm": "video/webm",
  ".mov": "video/quicktime",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".ogg": "audio/ogg",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".pdf": "application/pdf",
  ".json": "application/json",
  ".txt": "text/plain",
  ".html": "text/html",
  ".htm": "text/html",
  ".css": "text/css",
  ".js": "text/javascript",
  ".xml": "application/xml",
  ".csv": "text/csv",
  ".zip": "application/zip",
};

function _guessContentType(name) {
  const ext = path.extname(String(name || "")).toLowerCase();
  return MIME_BY_EXT[ext] || null;
}

class SoAPI {
  constructor(client) {
    this._c = client;
  }

  async listBuckets() {
    this._c.requireConsole();
    const data = await this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/storage/buckets`
    );
    return data.items || [];
  }

  async createBucket(name) {
    this._c.requireConsole();
    return this._c.consoleRequest("POST", `accounts/${this._c.accountId}/storage/buckets`, {
      json: { name: String(name).trim().toLowerCase() },
    });
  }

  async deleteBucket(name) {
    this._c.requireConsole();
    await this._c.consoleRequest(
      "DELETE",
      `accounts/${this._c.accountId}/storage/buckets/${String(name).trim().toLowerCase()}`
    );
  }

  async listObjects(bucketName, { prefix = "", recursive = false, page = 1, pageSize = 100 } = {}) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${bucketName}/objects`;
    return this._c.dataPlaneRequest("so", "GET", reqPath, {
      params: { prefix, recursive, page, page_size: pageSize },
    });
  }

  async listAllObjects(bucketName, { prefix = "", recursive = true } = {}) {
    const items = [];
    let page = 1;
    for (;;) {
      const data = await this.listObjects(bucketName, { prefix, recursive, page, pageSize: 100 });
      for (const item of data.items || []) {
        if (!item.is_dir) items.push(item);
      }
      if (page >= Number(data.pages || 1)) break;
      page += 1;
    }
    return items;
  }

  async upload(bucketName, filePath, { key, body, contentType } = {}) {
    this._c.requireAccessKey();
    const hasBody = body !== undefined && body !== null;
    if (hasBody && filePath != null && filePath !== "") {
      throw new HomeCloudError("Pass either filePath or body, not both");
    }
    if (!hasBody && (filePath == null || filePath === "")) {
      throw new HomeCloudError("filePath or body is required");
    }
    if (hasBody && (!key || !String(key).trim())) {
      throw new HomeCloudError("key is required when uploading body");
    }

    let objectKey;
    let filename;
    let payload;

    if (hasBody) {
      objectKey = String(key).trim().replace(/^\/+/, "");
      filename = path.basename(objectKey) || "object";
      payload = body;
    } else {
      if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
        throw new HomeCloudError(`File not found: ${filePath}`);
      }
      objectKey = key || path.basename(filePath);
      filename = path.basename(filePath);
      payload = fs.readFileSync(filePath);
    }

    const mime =
      contentType ||
      _guessContentType(objectKey) ||
      _guessContentType(filename) ||
      "application/octet-stream";
    const accountId = this._c.accountId;
    const uploadPath = `/${accountId}/${bucketName}/objects`;
    const form = new FormData();
    form.append("key", objectKey);
    form.append("file", new Blob([payload], { type: mime }), filename);
    return this._c.dataPlaneRequest("so", "POST", uploadPath, { formData: form });
  }

  async putJson(bucketName, objectKey, value) {
    const data = Buffer.from(JSON.stringify(value, null, 2), "utf8");
    return this.upload(bucketName, null, {
      key: objectKey,
      body: data,
      contentType: "application/json",
    });
  }

  async delete(bucketName, objectKey) {
    this._c.requireAccessKey();
    const { signPath, urlPath } = soObjectPaths(this._c.accountId, bucketName, objectKey);
    await this._c.dataPlaneRequest("so", "DELETE", signPath, { urlPath, signPath });
  }

  async download(bucketName, objectKey, { destPath } = {}) {
    this._c.requireAccessKey();
    if (!destPath) throw new HomeCloudError("destPath is required");
    const key = String(objectKey).replace(/^\/+/, "");
    const { signPath, urlPath } = soObjectPaths(this._c.accountId, bucketName, key);
    const buf = await this._c.dataPlaneRequestBytes("so", "GET", signPath, { urlPath, signPath });
    fs.mkdirSync(path.dirname(destPath), { recursive: true });
    fs.writeFileSync(destPath, buf);
    return { key, size: buf.length, path: destPath };
  }

  async headObject(bucketName, objectKey) {
    this._c.requireAccessKey();
    const key = String(objectKey).replace(/^\/+/, "");
    const { signPath, urlPath } = soObjectPaths(this._c.accountId, bucketName, key);
    const raw = await this._c.dataPlaneRequest("so", "GET", `${signPath}/metadata`, {
      urlPath: `${urlPath}/metadata`,
      signPath: `${signPath}/metadata`,
    });
    if (!raw || typeof raw !== "object") throw new HomeCloudError("Invalid metadata response");
    const userMeta = raw.metadata && typeof raw.metadata === "object" ? raw.metadata : {};
    const tags = raw.tags && typeof raw.tags === "object" ? raw.tags : {};
    return {
      key: String(raw.key || key),
      size: Number(raw.size || 0),
      etag: raw.etag,
      content_type: raw.content_type,
      last_modified: raw.last_modified,
      metadata: Object.fromEntries(Object.entries(userMeta).map(([k, v]) => [String(k), String(v)])),
      tags: Object.fromEntries(Object.entries(tags).map(([k, v]) => [String(k), String(v)])),
    };
  }

  async objectMetadata(bucketName, objectKey) {
    return this.headObject(bucketName, objectKey);
  }

  async getObjectUri(bucketName, objectKey) {
    this._c.requireAccessKey();
    const key = String(objectKey).replace(/^\/+/, "");
    const { signPath, urlPath } = soObjectPaths(this._c.accountId, bucketName, key);
    const raw = await this._c.dataPlaneRequest("so", "GET", `${signPath}/uri`, {
      urlPath: `${urlPath}/uri`,
      signPath: `${signPath}/uri`,
    });
    if (!raw || typeof raw !== "object") throw new HomeCloudError("Invalid URI response");
    return {
      so_uri: String(raw.so_uri || `so://${bucketName}/${key}`),
      https_url: String(raw.https_url || ""),
      https_requires_public: Boolean(raw.https_requires_public ?? true),
    };
  }

  async generatePresignedUrl(bucketName, objectKey, { expires = 3600 } = {}) {
    this._c.requireAccessKey();
    const key = String(objectKey).replace(/^\/+/, "");
    const { signPath, urlPath } = soObjectPaths(this._c.accountId, bucketName, key);
    const raw = await this._c.dataPlaneRequest("so", "GET", `${signPath}/presigned`, {
      urlPath: `${urlPath}/presigned`,
      signPath: `${signPath}/presigned`,
      params: { expires },
    });
    if (!raw || !raw.url) throw new HomeCloudError("Invalid presigned URL response");
    return {
      url: String(raw.url),
      expires_in_seconds: Number(raw.expires_in_seconds || expires),
    };
  }

  async copy(bucketName, sourceKey, destinationKey, { sourceBucket = null } = {}) {
    this._c.requireAccessKey();
    const { signPath, urlPath } = soObjectPaths(this._c.accountId, bucketName, sourceKey);
    return this._c.dataPlaneRequest("so", "POST", `${signPath}/copy`, {
      urlPath: `${urlPath}/copy`,
      signPath: `${signPath}/copy`,
      json: {
        destination_key: destinationKey,
        source_bucket: sourceBucket || null,
      },
    });
  }

  async deleteRecursive(bucketName, prefix = "") {
    const items = await this.listAllObjects(bucketName, { prefix, recursive: true });
    for (const item of items) {
      await this.delete(bucketName, item.key);
    }
    return items.length;
  }

  _isSoUri(target) {
    const lowered = String(target || "").toLowerCase();
    return lowered.startsWith("so://") || lowered.startsWith("s3://");
  }

  _parseSoUri(target) {
    let text = String(target || "").trim();
    const lowered = text.toLowerCase();
    if (lowered.startsWith("so://")) text = text.slice(5);
    else if (lowered.startsWith("s3://")) text = text.slice(5);
    text = text.replace(/^\/+|\/+$/g, "");
    if (!text) throw new HomeCloudError("URI must include a bucket name");
    const slash = text.indexOf("/");
    if (slash < 0) return { bucket: text, prefix: "" };
    return { bucket: text.slice(0, slash), prefix: text.slice(slash + 1) };
  }

  _syncJoinPrefix(prefixClean, relative) {
    const rel = String(relative || "").replace(/^\/+/, "");
    if (!prefixClean) return rel;
    if (!rel) return prefixClean;
    return `${prefixClean}/${rel}`;
  }

  _syncRelativePath(key, prefixClean) {
    if (!prefixClean) return key;
    if (key === prefixClean) return key.split("/").pop();
    if (key.startsWith(`${prefixClean}/`)) return key.slice(prefixClean.length + 1);
    return key;
  }

  /**
   * Unified sync: local↔bucket or bucket↔bucket.
   * Prefer this over syncLocalToBucket / syncBucketToLocal.
   */
  async sync(source, destination, { deleteExtra = false, skip = false } = {}) {
    const srcRemote = this._isSoUri(source);
    const dstRemote = this._isSoUri(destination);
    if (srcRemote && dstRemote) {
      const src = this._parseSoUri(source);
      const dst = this._parseSoUri(destination);
      return this._syncBucketToBucket(src.bucket, dst.bucket, {
        sourcePrefix: src.prefix,
        destinationPrefix: dst.prefix,
        deleteExtra,
        skip,
      });
    }
    if (srcRemote && !dstRemote) {
      const src = this._parseSoUri(source);
      return this.syncBucketToLocal(src.bucket, destination, {
        prefix: src.prefix,
        deleteExtra,
        skip,
      });
    }
    if (!srcRemote && dstRemote) {
      const dst = this._parseSoUri(destination);
      return this.syncLocalToBucket(source, dst.bucket, {
        prefix: dst.prefix,
        deleteExtra,
        skip,
      });
    }
    throw new HomeCloudError(
      "One or both sides must be an so:// URI (local↔bucket or bucket↔bucket)"
    );
  }

  async _syncBucketToBucket(
    sourceBucket,
    destinationBucket,
    { sourcePrefix = "", destinationPrefix = "", deleteExtra = false, skip = false } = {}
  ) {
    this._c.requireAccessKey();
    const srcPrefix = String(sourcePrefix || "").replace(/^\/+|\/+$/g, "");
    const dstPrefix = String(destinationPrefix || "").replace(/^\/+|\/+$/g, "");
    if (sourceBucket === destinationBucket && srcPrefix === dstPrefix) {
      throw new HomeCloudError(`Source and destination are the same: so://${sourceBucket}/${srcPrefix}`);
    }

    const sourceItems = await this.listAllObjects(sourceBucket, {
      prefix: srcPrefix,
      recursive: true,
    });
    const destItems = await this.listAllObjects(destinationBucket, {
      prefix: dstPrefix,
      recursive: true,
    });

    const sourceRels = new Map();
    for (const item of sourceItems) {
      const rel = this._syncRelativePath(item.key, srcPrefix);
      sourceRels.set(rel, { key: item.key, size: Number(item.size || 0) });
    }
    const destRels = new Map();
    for (const item of destItems) {
      const rel = this._syncRelativePath(item.key, dstPrefix);
      destRels.set(rel, { key: item.key, size: Number(item.size || 0) });
    }

    let copied = 0;
    let skipped = 0;
    for (const [rel, src] of sourceRels) {
      const dest = destRels.get(rel);
      if (skip && dest && dest.size === src.size) {
        skipped += 1;
        continue;
      }
      const dstKey = this._syncJoinPrefix(dstPrefix, rel);
      await this.copy(destinationBucket, src.key, dstKey, {
        sourceBucket: sourceBucket !== destinationBucket ? sourceBucket : null,
      });
      copied += 1;
    }

    let deleted = 0;
    if (deleteExtra) {
      for (const [rel, dest] of destRels) {
        if (sourceRels.has(rel)) continue;
        await this.delete(destinationBucket, dest.key);
        deleted += 1;
      }
    }
    return { copied, skipped, deleted };
  }

  /** Prefer sync("./dir", "so://bucket/prefix"). */
  async syncLocalToBucket(localDir, bucketName, { prefix = "", deleteExtra = false, skip = false } = {}) {
    this._c.requireAccessKey();
    const root = path.resolve(localDir);
    const prefixClean = String(prefix || "").replace(/^\/+|\/+$/g, "");
    const walk = (dir, base) => {
      const out = [];
      for (const name of fs.readdirSync(dir)) {
        const full = path.join(dir, name);
        const st = fs.statSync(full);
        const rel = path.relative(base, full).split(path.sep).join("/");
        if (st.isDirectory()) out.push(...walk(full, base));
        else out.push({ rel, size: st.size });
      }
      return out;
    };
    const locals = walk(root, root);
    const remote = await this.listAllObjects(bucketName, { prefix: prefixClean, recursive: true });
    const remoteByKey = new Map(remote.map((item) => [item.key, item]));

    let uploaded = 0;
    let skipped = 0;
    for (const { rel, size } of locals) {
      const key = this._syncJoinPrefix(prefixClean, rel);
      const existing = remoteByKey.get(key);
      if (skip && existing && Number(existing.size || 0) === size) {
        skipped += 1;
        continue;
      }
      await this.upload(bucketName, path.join(root, rel), { key });
      uploaded += 1;
    }
    let deleted = 0;
    if (deleteExtra) {
      const localKeys = new Set(locals.map(({ rel }) => this._syncJoinPrefix(prefixClean, rel)));
      for (const item of remote) {
        if (!localKeys.has(item.key)) {
          await this.delete(bucketName, item.key);
          deleted += 1;
        }
      }
    }
    return { uploaded, skipped, deleted };
  }

  /** Prefer sync("so://bucket/prefix", "./dir"). */
  async syncBucketToLocal(bucketName, localDir, { prefix = "", deleteExtra = false, skip = false } = {}) {
    this._c.requireAccessKey();
    const root = path.resolve(localDir);
    const prefixClean = String(prefix || "").replace(/^\/+|\/+$/g, "");
    const items = await this.listAllObjects(bucketName, { prefix: prefixClean, recursive: true });
    let downloaded = 0;
    let skippedCount = 0;
    const remoteRels = new Set();
    for (const item of items) {
      const rel = this._syncRelativePath(item.key, prefixClean);
      remoteRels.add(rel);
      const dest = path.join(root, rel);
      if (
        skip &&
        fs.existsSync(dest) &&
        fs.statSync(dest).isFile() &&
        fs.statSync(dest).size === Number(item.size || 0)
      ) {
        skippedCount += 1;
        continue;
      }
      await this.download(bucketName, item.key, { destPath: dest });
      downloaded += 1;
    }
    let deleted = 0;
    if (deleteExtra && fs.existsSync(root)) {
      const walk = (dir, base) => {
        const out = [];
        for (const name of fs.readdirSync(dir)) {
          const full = path.join(dir, name);
          const st = fs.statSync(full);
          if (st.isDirectory()) out.push(...walk(full, base));
          else out.push(path.relative(base, full).split(path.sep).join("/"));
        }
        return out;
      };
      for (const rel of walk(root, root)) {
        if (remoteRels.has(rel)) continue;
        fs.unlinkSync(path.join(root, rel));
        deleted += 1;
      }
    }
    return { downloaded, skipped: skippedCount, deleted };
  }
}

module.exports = { SoAPI };
