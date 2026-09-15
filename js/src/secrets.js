"use strict";

class SecretsAPI {
  constructor(client) {
    this._c = client;
  }

  /** Console JWT — list secret metadata. */
  async list() {
    this._c.requireConsole();
    const data = await this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/secrets`
    );
    return data.items || [];
  }

  /** Data plane — secret metadata by name (Access Key). */
  async get(secretName) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/secrets/${encodeURIComponent(secretName)}`;
    return this._c.dataPlaneRequest("secrets", "GET", reqPath);
  }

  /** Data plane — secret values map (Access Key). */
  async getValue(secretName) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/secrets/${encodeURIComponent(secretName)}/value`;
    return this._c.dataPlaneRequest("secrets", "GET", reqPath);
  }

  /** Data plane — replace entire values map (Access Key). */
  async putValue(secretName, values) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/secrets/${encodeURIComponent(secretName)}/value`;
    return this._c.dataPlaneRequest("secrets", "PUT", reqPath, {
      json: { values },
    });
  }
}

module.exports = { SecretsAPI };
