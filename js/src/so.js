"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");
const { soObjectPaths } = require("./signing");
const { HomeCloudError } = require("./errors");

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

  async upload(bucketName, filePath, { key } = {}) {
    this._c.requireAccessKey();
    if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
      throw new HomeCloudError(`File not found: ${filePath}`);
    }
    const objectKey = key || path.basename(filePath);
    const accountId = this._c.accountId;
    const uploadPath = `/${accountId}/${bucketName}/objects`;
    const blob = fs.readFileSync(filePath);
    const form = new FormData();
    form.append("key", objectKey);
    form.append("file", new Blob([blob]), path.basename(filePath));
    return this._c.dataPlaneRequest("so", "POST", uploadPath, { formData: form });
  }

  async putJson(bucketName, objectKey, value) {
    const tmp = path.join(
      os.tmpdir(),
      `hc-sdk-${Date.now()}-${Math.random().toString(16).slice(2)}.json`
    );
    fs.writeFileSync(tmp, JSON.stringify(value, null, 2), "utf8");
    try {
      return await this.upload(bucketName, tmp, { key: objectKey });
    } finally {
      try {
        fs.unlinkSync(tmp);
      } catch (_) {}
    }
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

  async deleteRecursive(bucketName, prefix = "") {
    const items = await this.listAllObjects(bucketName, { prefix, recursive: true });
    for (const item of items) {
      await this.delete(bucketName, item.key);
    }
    return items.length;
  }

  async syncLocalToBucket(localDir, bucketName, { prefix = "", deleteExtra = false } = {}) {
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
        else out.push(rel);
      }
      return out;
    };
    const locals = walk(root, root);
    for (const rel of locals) {
      const key = prefixClean ? `${prefixClean}/${rel}` : rel;
      await this.upload(bucketName, path.join(root, rel), { key });
    }
    if (deleteExtra) {
      const remote = await this.listAllObjects(bucketName, { prefix: prefixClean, recursive: true });
      const localKeys = new Set(
        locals.map((rel) => (prefixClean ? `${prefixClean}/${rel}` : rel))
      );
      for (const item of remote) {
        if (!localKeys.has(item.key)) await this.delete(bucketName, item.key);
      }
    }
    return { uploaded: locals.length };
  }

  async syncBucketToLocal(bucketName, localDir, { prefix = "" } = {}) {
    this._c.requireAccessKey();
    const root = path.resolve(localDir);
    const prefixClean = String(prefix || "").replace(/^\/+|\/+$/g, "");
    const items = await this.listAllObjects(bucketName, { prefix: prefixClean, recursive: true });
    for (const item of items) {
      let rel = item.key;
      if (prefixClean && item.key.startsWith(`${prefixClean}/`)) {
        rel = item.key.slice(prefixClean.length + 1);
      } else if (prefixClean && item.key === prefixClean) {
        rel = path.basename(item.key);
      }
      const dest = path.join(root, rel);
      await this.download(bucketName, item.key, { destPath: dest });
    }
    return { downloaded: items.length };
  }
}

module.exports = { SoAPI };
