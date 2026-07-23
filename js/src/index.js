"use strict";

const crypto = require("crypto");
const { URL } = require("url");
const fs = require("fs");
const path = require("path");

const DEFAULT_APEX = "holab.abrdns.com";

function soUrl(apex) {
  return `https://so.${apex || DEFAULT_APEX}`;
}
function mqUrl(apex) {
  return `https://mq.${apex || DEFAULT_APEX}`;
}
function secretsUrl(apex) {
  return `https://secrets.${apex || DEFAULT_APEX}`;
}
function mailApiUrl(apex) {
  return `https://mailapi.${apex || DEFAULT_APEX}`;
}

function buildStringToSign({ method, path: reqPath, timestamp, accountId }) {
  return `${String(method).toUpperCase()}\n${reqPath}\n${timestamp}\n${accountId}`;
}

function signRequestHeaders({
  accessKeyId,
  secret,
  method,
  path: reqPath,
  accountId,
  sessionToken,
}) {
  const ts = new Date();
  const timestamp = ts.toISOString().replace(/\.\d{3}Z$/, "Z");
  const stringToSign = buildStringToSign({
    method,
    path: reqPath,
    timestamp,
    accountId,
  });
  const signature = crypto.createHmac("sha256", secret).update(stringToSign).digest("hex");
  const headers = {
    "X-Homecloud-Access-Key-Id": accessKeyId,
    "X-Homecloud-Date": timestamp,
    "X-Homecloud-Signature": signature,
  };
  if (sessionToken) headers["X-Homecloud-Session-Token"] = sessionToken;
  return headers;
}

class HomeCloudError extends Error {
  constructor(message, { statusCode, detail } = {}) {
    super(message);
    this.name = "HomeCloudError";
    this.statusCode = statusCode;
    this.detail = detail;
  }
}

class HomeCloud {
  constructor({
    accessKeyId,
    secretAccessKey,
    accountId,
    apex = DEFAULT_APEX,
    sessionToken,
    dataPlaneBases,
  }) {
    this.accessKeyId = accessKeyId;
    this.secretAccessKey = secretAccessKey;
    this.accountId = accountId;
    this.apex = apex || DEFAULT_APEX;
    this.sessionToken = sessionToken || null;
    this.dataPlaneBases = dataPlaneBases || {};
    this.so = new SoAPI(this);
    this.mq = new MqAPI(this);
    this.secrets = new SecretsAPI(this);
    this.mail = new MailAPI(this);
  }

  static fromSts(sts, { accountId, apex } = {}) {
    const aid = accountId || process.env.HC_ACCOUNT_ID || "";
    let base = String(sts.base_url || sts.mail_base_url || "").replace(/\/$/, "");
    const resourceType = String(sts.resource_type || "").trim().toLowerCase();
    let resolvedApex = apex || process.env.HC_APEX || DEFAULT_APEX;
    const dataPlaneBases = {};
    if (base) {
      let host = "";
      try {
        host = new URL(base).hostname || "";
      } catch (_) {
        host = "";
      }
      if (resourceType === "mail") {
        if (host.startsWith("console.") || base.includes("/api/v1")) {
          if (host.startsWith("console.")) resolvedApex = resolvedApex || host.slice("console.".length);
          dataPlaneBases.mail = mailApiUrl(resolvedApex).replace(/\/$/, "");
        } else {
          dataPlaneBases.mail = base;
          if (host.startsWith("mailapi.")) resolvedApex = resolvedApex || host.slice("mailapi.".length);
        }
      } else if (["so", "mq", "secrets"].includes(resourceType)) {
        dataPlaneBases[resourceType] = base;
        const prefix = `${resourceType}.`;
        if (host.startsWith(prefix)) resolvedApex = resolvedApex || host.slice(prefix.length);
      }
    } else if (resourceType === "mail") {
      dataPlaneBases.mail = mailApiUrl(resolvedApex).replace(/\/$/, "");
    }
    return new HomeCloud({
      accessKeyId: String(sts.access_key_id),
      secretAccessKey: String(sts.secret_access_key),
      accountId: aid,
      apex: resolvedApex || DEFAULT_APEX,
      sessionToken: sts.session_token ? String(sts.session_token) : null,
      dataPlaneBases,
    });
  }

  static fromFunctionContext(context, { binding }) {
    const ctx = context || {};
    let stsMap = Object.assign({}, ctx.sts || {});
    if (!Object.keys(stsMap).length && process.env.HC_STS_JSON) {
      try {
        stsMap = JSON.parse(process.env.HC_STS_JSON);
      } catch (_) {
        stsMap = {};
      }
    }
    const entry = stsMap[binding];
    if (!entry || !entry.access_key_id) {
      throw new HomeCloudError(`STS binding '${binding}' not found in context.sts`);
    }
    return HomeCloud.fromSts(entry, {
      accountId: ctx.account_id || ctx.accountId || process.env.HC_ACCOUNT_ID,
    });
  }

  baseUrl(service) {
    if (this.dataPlaneBases[service]) return this.dataPlaneBases[service].replace(/\/$/, "");
    if (service === "so") return soUrl(this.apex);
    if (service === "mq") return mqUrl(this.apex);
    if (service === "secrets") return secretsUrl(this.apex);
    if (service === "mail") return mailApiUrl(this.apex);
    throw new HomeCloudError(`Unknown data-plane service: ${service}`);
  }

  async dataPlaneRequest(service, method, reqPath, { json, formData, body, headers } = {}) {
    const base = this.baseUrl(service);
    const url = new URL(reqPath.startsWith("http") ? reqPath : `${base}${reqPath}`);
    const signPath = url.pathname + (url.search || "");
    const auth = signRequestHeaders({
      accessKeyId: this.accessKeyId,
      secret: this.secretAccessKey,
      method,
      path: url.pathname,
      accountId: this.accountId,
      sessionToken: this.sessionToken,
    });
    const init = {
      method,
      headers: { ...auth, ...(headers || {}) },
    };
    if (formData) {
      init.body = formData;
    } else if (json !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(json);
    } else if (body !== undefined) {
      init.body = body;
    }
    const res = await fetch(url, init);
    const text = await res.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (_) {
        data = { raw: text };
      }
    }
    if (!res.ok) {
      throw new HomeCloudError(
        (data && (data.detail || data.message || data.error)) || `HTTP ${res.status}`,
        { statusCode: res.status, detail: data }
      );
    }
    return data;
  }
}

class SoAPI {
  constructor(client) {
    this._c = client;
  }

  async upload(bucketName, filePath, { key } = {}) {
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
      require("os").tmpdir(),
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
}

class MqAPI {
  constructor(client) {
    this._c = client;
  }

  async send(queueName, body, { headers } = {}) {
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/messages`;
    const bodyStr = typeof body === "string" ? body : JSON.stringify(body);
    const payload = { body: bodyStr };
    if (headers) payload.headers = headers;
    return this._c.dataPlaneRequest("mq", "POST", reqPath, { json: payload });
  }
}

class SecretsAPI {
  constructor(client) {
    this._c = client;
  }

  async get(secretName) {
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/secrets/${encodeURIComponent(secretName)}`;
    return this._c.dataPlaneRequest("secrets", "GET", reqPath);
  }
}

class MailAPI {
  constructor(client) {
    this._c = client;
  }

  async listMessages({ mailbox = "INBOX", limit = 20 } = {}) {
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/mailboxes/${encodeURIComponent(mailbox)}/messages?limit=${limit}`;
    return this._c.dataPlaneRequest("mail", "GET", reqPath);
  }
}

module.exports = {
  HomeCloud,
  HomeCloudError,
  signRequestHeaders,
  soUrl,
  mqUrl,
  secretsUrl,
  mailApiUrl,
  DEFAULT_APEX,
};
