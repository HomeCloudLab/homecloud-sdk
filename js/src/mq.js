"use strict";

class MqAPI {
  constructor(client) {
    this._c = client;
  }

  async send(queueName, body, { headers } = {}) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/messages`;
    const bodyStr = typeof body === "string" ? body : JSON.stringify(body);
    const payload = { body: bodyStr };
    if (headers) payload.headers = headers;
    return this._c.dataPlaneRequest("mq", "POST", reqPath, { json: payload });
  }

  async receive(queueName, { maxMessages = 1, waitSeconds = 20 } = {}) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/messages`;
    const data = await this._c.dataPlaneRequest("mq", "GET", reqPath, {
      params: { max_messages: maxMessages, wait_seconds: waitSeconds },
    });
    return data.items || [];
  }
}

module.exports = { MqAPI };
