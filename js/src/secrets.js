"use strict";

function normalizeKeys(keys) {
  if (keys == null) return undefined;
  const items = Array.isArray(keys) ? keys : [keys];
  const out = [];
  const seen = new Set();
  for (const item of items) {
    for (const part of String(item).split(",")) {
      const key = part.trim();
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push(key);
    }
  }
  return out.length ? out : undefined;
}

class SecretsAPI {
  constructor(client) {
    this._c = client;
  }

  /**
   * Create secret — Access Key SigV1 preferred (no console login).
   * @param {string} secretName
   * @param {{ description?: string, values?: Record<string,string> }} [opts]
   */
  async create(secretName, opts = {}) {
    const body = { name: secretName };
    if (opts.description != null) body.description = opts.description;
    const path = `accounts/${this._c.accountId}/secrets`;
    let created;
    if (this._c.hasAccessKey) {
      created = await this._c.consoleSignedRequest("POST", path, { json: body });
    } else {
      this._c.requireConsole();
      created = await this._c.consoleRequest("POST", path, { json: body });
    }
    const values = opts.values;
    if (!values || typeof values !== "object") return created;
    const logical = (created && created.name) || secretName;
    return this.putValue(logical, values);
  }

  /** List secret metadata — Access Key SigV1 preferred. */
  async list() {
    const path = `accounts/${this._c.accountId}/secrets`;
    if (this._c.hasAccessKey) {
      const data = await this._c.consoleSignedRequest("GET", path);
      return data.items || [];
    }
    this._c.requireConsole();
    const data = await this._c.consoleRequest("GET", path);
    return data.items || [];
  }

  /** Data plane — secret metadata by name (Access Key). */
  async get(secretName) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/secrets/${encodeURIComponent(secretName)}`;
    return this._c.dataPlaneRequest("secrets", "GET", reqPath);
  }

  /**
   * Data plane — get secret values (Access Key).
   * @param {string} secretName
   * @param {{ keys?: string|string[] }} [opts] optional key filter
   */
  async getValue(secretName, opts = {}) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/secrets/${encodeURIComponent(secretName)}/value`;
    const keys = normalizeKeys(opts.keys);
    return this._c.dataPlaneRequest("secrets", "GET", reqPath, {
      params: keys ? { keys } : undefined,
    });
  }

  /**
   * Data plane — put secret values (Access Key).
   * @param {string} secretName
   * @param {Record<string,string>} values
   * @param {{ merge?: boolean }} [opts] merge=true upserts keys
   */
  async putValue(secretName, values, opts = {}) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/secrets/${encodeURIComponent(secretName)}/value`;
    const body = { values };
    if (opts.merge) body.mode = "merge";
    return this._c.dataPlaneRequest("secrets", "PUT", reqPath, {
      json: body,
    });
  }
}

module.exports = { SecretsAPI };
