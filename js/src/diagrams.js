"use strict";

class DiagramsAPI {
  constructor(client) {
    this._c = client;
  }

  async _request(method, path, { json, params } = {}) {
    await this._c.ensureAccountId();
    if (this._c.hasAccessKey) {
      return this._c.consoleSignedRequest(method, path, { json, params });
    }
    this._c.requireConsole();
    return this._c.consoleRequest(method, path, { json, params });
  }

  async list() {
    const data = await this._request(
      "GET",
      `accounts/${this._c.accountId}/diagrams`
    );
    return data.items || [];
  }

  async get(diagramId) {
    return this._request(
      "GET",
      `accounts/${this._c.accountId}/diagrams/${encodeURIComponent(diagramId)}`
    );
  }

  async create(name, { description, document } = {}) {
    const json = { name };
    if (description != null) json.description = description;
    if (document != null) json.document = document;
    return this._request("POST", `accounts/${this._c.accountId}/diagrams`, {
      json,
    });
  }

  async update(diagramId, { name, description, document, revision } = {}) {
    const json = {};
    if (name != null) json.name = name;
    if (description != null) json.description = description;
    if (document != null) json.document = document;
    if (revision != null) json.revision = revision;
    return this._request(
      "PATCH",
      `accounts/${this._c.accountId}/diagrams/${encodeURIComponent(diagramId)}`,
      { json }
    );
  }
}

module.exports = { DiagramsAPI };
