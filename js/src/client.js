"use strict";

const { URL } = require("url");
const {
  DEFAULT_APEX,
  WHOAMI_PATH,
  WHOAMI_ACCOUNT_SENTINEL,
  soUrl,
  mqUrl,
  secretsUrl,
  mailApiUrl,
  consoleUrl,
  functionUrl,
  envFirst,
} = require("./defaults");
const { signRequestHeaders } = require("./signing");
const {
  HomeCloudError,
  NotConfiguredError,
  NotLoggedInError,
  errorFromStatus,
} = require("./errors");
const { resolveProfile, loadSession, saveSession } = require("./credentials");
const { SoAPI } = require("./so");
const { MqAPI } = require("./mq");
const { SecretsAPI } = require("./secrets");
const { MailAPI } = require("./mail");
const { AccountsAPI, AppsAPI, QueuesAPI, FunctionsAPI } = require("./management");

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

class HomeCloud {
  constructor(opts = {}) {
    this.accessKeyId = opts.accessKeyId || opts.access_key_id || null;
    this.secretAccessKey = opts.secretAccessKey || opts.secret_access_key || null;
    this.accountId = opts.accountId || opts.account_id || null;
    this.apex = opts.apex || DEFAULT_APEX;
    this.sessionToken = opts.sessionToken || opts.session_token || null;
    this.accessToken = opts.accessToken || opts.access_token || null;
    this.dataPlaneBases = Object.assign({}, opts.dataPlaneBases || opts.data_plane_bases || {});
    this.consoleBaseUrl = opts.consoleBaseUrl || opts.console_base_url || null;
    this.profileName = opts.profileName || opts.profile || null;
    this.timeoutMs = opts.timeoutMs || 30000;

    this.so = new SoAPI(this);
    this.storage = this.so;
    this.mq = new MqAPI(this);
    this.secrets = new SecretsAPI(this);
    this.mail = new MailAPI(this);
    this.accounts = new AccountsAPI(this);
    this.apps = new AppsAPI(this);
    this.queues = new QueuesAPI(this);
    this.functions = new FunctionsAPI(this);
  }

  static fromEnv(opts = {}) {
    return HomeCloud.fromProfile(opts.profile || null, opts);
  }

  static fromProfile(profile, opts = {}) {
    const resolved = resolveProfile(profile);
    return new HomeCloud({
      ...opts,
      profileName: resolved.profileName,
      accessKeyId: opts.accessKeyId || resolved.accessKeyId,
      secretAccessKey: opts.secretAccessKey || resolved.secretAccessKey,
      accountId: opts.accountId || resolved.accountId,
      apex: opts.apex || resolved.apex,
      accessToken: opts.accessToken || resolved.accessToken,
    });
  }

  static fromCredentials(accessKeyId, secretAccessKey, opts = {}) {
    return new HomeCloud({
      ...opts,
      accessKeyId,
      secretAccessKey,
      accountId: opts.accountId,
      apex: opts.apex,
      sessionToken: opts.sessionToken,
    });
  }

  static fromSts(sts, { accountId, apex } = {}) {
    const aid = accountId || process.env.HC_ACCOUNT_ID || envFirst("HOMECLOUD_ACCOUNT_ID") || "";
    let base = String(sts.base_url || sts.mail_base_url || "").replace(/\/$/, "");
    const resourceType = String(sts.resource_type || "").trim().toLowerCase();
    let resolvedApex = apex || envFirst("HOMECLOUD_APEX", "HC_APEX") || DEFAULT_APEX;
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

  requireAccessKey() {
    if (!this.accessKeyId || !this.secretAccessKey) {
      throw new NotConfiguredError(
        "Access Key not configured. Run: homecloud configure, or set HOMECLOUD_ACCESS_KEY_ID"
      );
    }
  }

  requireConsole() {
    if (!this.accessToken) throw new NotLoggedInError();
  }

  baseUrl(service) {
    if (this.dataPlaneBases[service]) return this.dataPlaneBases[service].replace(/\/$/, "");
    if (service === "so") return soUrl(this.apex);
    if (service === "mq") return mqUrl(this.apex);
    if (service === "secrets") return secretsUrl(this.apex);
    if (service === "mail") return mailApiUrl(this.apex);
    throw new HomeCloudError(`Unknown data-plane service: ${service}`);
  }

  async ensureAccountId() {
    if (this.accountId) return this.accountId;
    this.requireAccessKey();
    const headers = signRequestHeaders({
      accessKeyId: this.accessKeyId,
      secret: this.secretAccessKey,
      method: "GET",
      path: WHOAMI_PATH,
      accountId: WHOAMI_ACCOUNT_SENTINEL,
      sessionToken: this.sessionToken,
    });
    const url = `${soUrl(this.apex).replace(/\/$/, "")}${WHOAMI_PATH}`;
    const res = await fetch(url, { method: "GET", headers });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw errorFromStatus(res.status, { detail: data, url });
    this.accountId = data.account_id;
    if (!this.accountId) throw new HomeCloudError("whoami did not return account_id");
    return this.accountId;
  }

  async dataPlaneRequest(
    service,
    method,
    reqPath,
    { json, formData, body, headers, params, urlPath, signPath } = {}
  ) {
    await this.ensureAccountId();
    this.requireAccessKey();
    const base = this.baseUrl(service);
    let pathForUrl = urlPath || reqPath;
    let pathForSign = signPath || reqPath.split("?")[0];
    if (params && Object.keys(params).length) {
      const u = new URL(pathForUrl.startsWith("http") ? pathForUrl : `${base}${pathForUrl}`);
      for (const [k, v] of Object.entries(params)) {
        if (v === undefined || v === null) continue;
        u.searchParams.set(k, String(v));
      }
      pathForUrl = u.pathname + u.search;
    }
    const url = new URL(pathForUrl.startsWith("http") ? pathForUrl : `${base}${pathForUrl}`);
    const auth = signRequestHeaders({
      accessKeyId: this.accessKeyId,
      secret: this.secretAccessKey,
      method,
      path: pathForSign || url.pathname,
      accountId: this.accountId,
      sessionToken: this.sessionToken,
    });
    const init = {
      method,
      headers: { ...auth, ...(headers || {}) },
      signal: AbortSignal.timeout(this.timeoutMs),
    };
    if (formData) init.body = formData;
    else if (json !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(json);
    } else if (body !== undefined) init.body = body;

    let lastErr;
    for (let attempt = 0; attempt < 3; attempt++) {
      const res = await fetch(url, init);
      if ([502, 503, 504].includes(res.status) && attempt < 2) {
        await sleep(500 * (attempt + 1));
        continue;
      }
      if (method === "DELETE" && res.status === 204) return null;
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
        lastErr = errorFromStatus(res.status, {
          detail: data && (data.detail !== undefined ? data.detail : data),
          url: String(url),
        });
        throw lastErr;
      }
      return data;
    }
    throw lastErr || new HomeCloudError("Request failed");
  }

  async dataPlaneRequestBytes(service, method, reqPath, { urlPath, signPath, params } = {}) {
    await this.ensureAccountId();
    this.requireAccessKey();
    const base = this.baseUrl(service);
    let pathForUrl = urlPath || reqPath;
    let pathForSign = signPath || reqPath.split("?")[0];
    if (params && Object.keys(params).length) {
      const u = new URL(`${base}${pathForUrl}`);
      for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
      pathForUrl = u.pathname + u.search;
    }
    const url = new URL(pathForUrl.startsWith("http") ? pathForUrl : `${base}${pathForUrl}`);
    const auth = signRequestHeaders({
      accessKeyId: this.accessKeyId,
      secret: this.secretAccessKey,
      method,
      path: pathForSign || url.pathname,
      accountId: this.accountId,
      sessionToken: this.sessionToken,
    });
    const res = await fetch(url, { method, headers: auth, signal: AbortSignal.timeout(this.timeoutMs) });
    if (!res.ok) {
      const text = await res.text();
      let data = null;
      try {
        data = JSON.parse(text);
      } catch (_) {
        data = text;
      }
      throw errorFromStatus(res.status, { detail: data, url: String(url) });
    }
    return Buffer.from(await res.arrayBuffer());
  }

  async consoleRequest(method, pathSeg, { json, params, requireAuth = true } = {}) {
    if (requireAuth) this.requireConsole();
    const base = (this.consoleBaseUrl || consoleUrl(this.apex)).replace(/\/$/, "");
    const url = new URL(`${base}/${String(pathSeg).replace(/^\/+/, "")}`);
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null) url.searchParams.set(k, String(v));
      }
    }
    const headers = {};
    if (requireAuth && this.accessToken) headers.Authorization = `Bearer ${this.accessToken}`;
    const init = { method, headers, signal: AbortSignal.timeout(this.timeoutMs) };
    if (json !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(json);
    }
    const res = await fetch(url, init);
    if (method === "DELETE" && res.status === 204) return null;
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
      throw errorFromStatus(res.status, {
        detail: data && (data.detail !== undefined ? data.detail : data),
        url: String(url),
      });
    }
    return data;
  }

  async consoleRequestBytes(method, pathSeg) {
    this.requireConsole();
    const base = (this.consoleBaseUrl || consoleUrl(this.apex)).replace(/\/$/, "");
    const url = `${base}/${String(pathSeg).replace(/^\/+/, "")}`;
    const res = await fetch(url, {
      method,
      headers: { Authorization: `Bearer ${this.accessToken}` },
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    if (!res.ok) {
      const text = await res.text();
      let data = null;
      try {
        data = JSON.parse(text);
      } catch (_) {
        data = text;
      }
      throw errorFromStatus(res.status, { detail: data, url });
    }
    return Buffer.from(await res.arrayBuffer());
  }

  async functionUrlRequest(functionName, payload) {
    this.requireAccessKey();
    await this.ensureAccountId();
    const pathSign = "/";
    const headers = signRequestHeaders({
      accessKeyId: this.accessKeyId,
      secret: this.secretAccessKey,
      method: "POST",
      path: pathSign,
      accountId: this.accountId,
      sessionToken: this.sessionToken,
    });
    headers["Content-Type"] = "application/json";
    const url = `${functionUrl(functionName, this.apex).replace(/\/$/, "")}/`;
    const res = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(payload || {}),
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    const text = await res.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch (_) {
        data = { raw: text };
      }
    }
    if (!res.ok) throw errorFromStatus(res.status, { detail: data, url });
    return data;
  }

  async login(username, password, { mfaCode } = {}) {
    const body = { username, password };
    if (mfaCode) body.mfa_code = mfaCode;
    const data = await this.consoleRequest("POST", "auth/login", {
      json: body,
      requireAuth: false,
    });
    const token = data.access_token;
    if (!token) throw new HomeCloudError("Login failed");
    this.accessToken = String(token);
    this._persistAccessToken();
  }

  async loginBrowser({ openBrowser = true, onWaiting, mfaToken } = {}) {
    const startBody = mfaToken ? { mfa_token: mfaToken } : {};
    const start = await this.consoleRequest("POST", "auth/cli/session", {
      json: startBody,
      requireAuth: false,
    });
    const sessionId = start.session_id;
    const verificationUri = start.verification_uri;
    if (!sessionId || !verificationUri) throw new HomeCloudError("Failed to start browser login session");
    const expiresIn = Number(start.expires_in || 600);
    const interval = Math.max(1, Number(start.interval || 2));
    const deadline = Date.now() + expiresIn * 1000;
    if (openBrowser) {
      try {
        const { exec } = require("child_process");
        const cmd =
          process.platform === "win32"
            ? `start "" "${verificationUri}"`
            : process.platform === "darwin"
              ? `open "${verificationUri}"`
              : `xdg-open "${verificationUri}"`;
        exec(cmd);
      } catch (_) {}
    }
    if (onWaiting) onWaiting(String(verificationUri));
    while (Date.now() < deadline) {
      const poll = await this.consoleRequest("GET", `auth/cli/session/${sessionId}`, {
        requireAuth: false,
      });
      const status = String(poll.status || "");
      if (status === "complete") {
        if (!poll.access_token) throw new HomeCloudError("Browser login completed without access token");
        this.accessToken = String(poll.access_token);
        this._persistAccessToken();
        return;
      }
      if (status === "expired") throw new HomeCloudError("Browser login session expired");
      await sleep(interval * 1000);
    }
    throw new HomeCloudError("Browser login timed out");
  }

  _persistAccessToken() {
    if (!this.profileName) return;
    const session = loadSession();
    session.profiles[this.profileName] = {
      ...(session.profiles[this.profileName] || {}),
      access_token: this.accessToken,
      active_account_id: this.accountId || undefined,
    };
    saveSession(session);
  }

  async accountIdResolved() {
    return this.ensureAccountId();
  }

  /** Sync helper matching Python client.account_id(). */
  account_id() {
    if (this.accountId) return this.accountId;
    throw new HomeCloudError("accountId not set — call await client.ensureAccountId() first");
  }
}

/** Node is async-native; alias kept for Python parity naming. */
const AsyncHomeCloud = HomeCloud;

module.exports = { HomeCloud, AsyncHomeCloud };
