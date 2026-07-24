"use strict";

class AccountsAPI {
  constructor(client) {
    this._c = client;
  }

  async list() {
    this._c.requireConsole();
    const data = await this._c.consoleRequest("GET", "accounts");
    return data.items || data || [];
  }

  async switch(accountRef) {
    this._c.requireConsole();
    return this._c.consoleRequest("POST", "accounts/switch", {
      json: { account: accountRef },
    });
  }
}

class AppsAPI {
  constructor(client) {
    this._c = client;
  }

  async list() {
    this._c.requireConsole();
    const data = await this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/applications`
    );
    return data.items || [];
  }
}

class QueuesAPI {
  constructor(client) {
    this._c = client;
  }

  async list({ live = false } = {}) {
    this._c.requireConsole();
    const data = await this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/queues`,
      { params: live ? { live: "true" } : undefined }
    );
    return data.items || [];
  }

  async get(queueName) {
    this._c.requireConsole();
    return this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/queues/${encodeURIComponent(queueName)}`
    );
  }
}

class FunctionsAPI {
  constructor(client) {
    this._c = client;
  }

  async list() {
    this._c.requireConsole();
    const data = await this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/functions`
    );
    return data.items || [];
  }

  async url(name) {
    this._c.requireConsole();
    return this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/functions/${name}/url`
    );
  }

  async enableUrl(name, { publicUrl = false, rateLimitPerMinute = 60 } = {}) {
    this._c.requireConsole();
    return this._c.consoleRequest(
      "POST",
      `accounts/${this._c.accountId}/functions/${name}/url/enable`,
      {
        json: {
          public_url_enabled: publicUrl,
          rate_limit_per_minute: rateLimitPerMinute,
        },
      }
    );
  }

  async disableUrl(name) {
    this._c.requireConsole();
    return this._c.consoleRequest(
      "POST",
      `accounts/${this._c.accountId}/functions/${name}/url/disable`
    );
  }

  async invoke(name, payload = {}) {
    this._c.requireAccessKey();
    return this._c.functionUrlRequest(name, payload);
  }

  async logs(name) {
    this._c.requireConsole();
    const data = await this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/functions/${name}/invocations`
    );
    return data.items || [];
  }

  async getInvocation(name, invocationId) {
    this._c.requireConsole();
    return this._c.consoleRequest(
      "GET",
      `accounts/${this._c.accountId}/functions/${name}/invocations/${invocationId}`
    );
  }
}

module.exports = { AccountsAPI, AppsAPI, QueuesAPI, FunctionsAPI };
