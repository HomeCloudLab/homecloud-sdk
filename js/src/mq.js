"use strict";

const MQ_BATCH_MAX = 10;

function entryBodyStr(value) {
  if (typeof value === "string") {
    if (!value) throw new Error("mq.send batch entry body must be non-empty");
    return value;
  }
  return JSON.stringify(value);
}

function buildMqBatchEntries(items) {
  if (!Array.isArray(items) || items.length < 1 || items.length > MQ_BATCH_MAX) {
    throw new Error(`mq.send batch requires 1–${MQ_BATCH_MAX} messages`);
  }
  const entries = [];
  const seenIds = new Set();
  for (let index = 0; index < items.length; index += 1) {
    const item = items[index];
    let entry;
    if (item && typeof item === "object" && typeof item.body === "string") {
      const entryId = item.id != null ? String(item.id) : String(index);
      if (!item.body) throw new Error("mq.send batch entry body must be non-empty");
      entry = { id: entryId, body: item.body };
      if (item.headers) entry.headers = item.headers;
    } else {
      entry = { id: String(index), body: entryBodyStr(item) };
    }
    if (seenIds.has(entry.id)) {
      throw new Error("mq.send batch entry ids must be unique");
    }
    seenIds.add(entry.id);
    entries.push(entry);
  }
  return entries;
}

class MqAPI {
  constructor(client) {
    this._c = client;
  }

  async send(queueName, body, { headers } = {}) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    if (Array.isArray(body)) {
      if (headers != null) {
        throw new Error("headers is only supported for single mq.send, not batch");
      }
      const reqPath = `/${accountId}/${queueName}/messages/batch`;
      return this._c.dataPlaneRequest("mq", "POST", reqPath, {
        json: { entries: buildMqBatchEntries(body) },
      });
    }
    const reqPath = `/${accountId}/${queueName}/messages`;
    const bodyStr = typeof body === "string" ? body : JSON.stringify(body);
    const payload = { body: bodyStr };
    if (headers) payload.headers = headers;
    return this._c.dataPlaneRequest("mq", "POST", reqPath, { json: payload });
  }

  async receive(queueName, { maxMessages = 1, waitSeconds = 20, delete = false } = {}) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/messages`;
    const params = { max_messages: maxMessages, wait_seconds: waitSeconds };
    if (delete) params.delete = "true";
    const data = await this._c.dataPlaneRequest("mq", "GET", reqPath, { params });
    return data.items || [];
  }

  async delete(queueName, sequence) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/messages/${sequence}`;
    await this._c.dataPlaneRequest("mq", "DELETE", reqPath);
  }

  async purge(queueName) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/purge`;
    await this._c.dataPlaneRequest("mq", "POST", reqPath);
  }

  async receiveDlq(queueName, { maxMessages = 1, waitSeconds = 20, delete = false } = {}) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/dlq/messages`;
    const params = { max_messages: maxMessages, wait_seconds: waitSeconds };
    if (delete) params.delete = "true";
    const data = await this._c.dataPlaneRequest("mq", "GET", reqPath, { params });
    return data.items || [];
  }

  async deleteDlq(queueName, sequence) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/dlq/messages/${sequence}`;
    await this._c.dataPlaneRequest("mq", "DELETE", reqPath);
  }

  async purgeDlq(queueName) {
    this._c.requireAccessKey();
    const accountId = this._c.accountId;
    const reqPath = `/${accountId}/${queueName}/dlq/purge`;
    await this._c.dataPlaneRequest("mq", "POST", reqPath);
  }
}

module.exports = { MqAPI, buildMqBatchEntries, MQ_BATCH_MAX };
