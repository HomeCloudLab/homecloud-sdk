"use strict";

const { HomeCloudError } = require("./errors");

function mailConsolePathToDataPlane(p, accountId) {
  const raw = String(p).replace(/^\/+/, "");
  const prefix = `accounts/${accountId}/mail/`;
  if (raw.startsWith(prefix)) return `/${accountId}/${raw.slice(prefix.length)}`;
  if (raw.startsWith(`${accountId}/`)) return `/${raw}`;
  throw new HomeCloudError(`Unexpected mail path for data plane: ${p}`);
}

class MailAPI {
  constructor(client) {
    this._c = client;
  }

  _useMailDataPlane() {
    return Boolean(this._c.accessKeyId && this._c.dataPlaneBases.mail);
  }

  async _mailRequest(method, consolePath, { params } = {}) {
    const accountId = this._c.accountId;
    if (this._useMailDataPlane()) {
      const dpPath = mailConsolePathToDataPlane(consolePath, accountId);
      return this._c.dataPlaneRequest("mail", method, dpPath, { params });
    }
    this._c.requireConsole();
    return this._c.consoleRequest(method, consolePath, { params });
  }

  async _mailRequestBytes(method, consolePath) {
    const accountId = this._c.accountId;
    if (this._useMailDataPlane()) {
      const dpPath = mailConsolePathToDataPlane(consolePath, accountId);
      return this._c.dataPlaneRequestBytes("mail", method, dpPath);
    }
    this._c.requireConsole();
    return this._c.consoleRequestBytes(method, consolePath);
  }

  async listMailboxes() {
    const accountId = this._c.accountId;
    const data = await this._mailRequest("GET", `accounts/${accountId}/mail/mailboxes`);
    return data.items || [];
  }

  async listMessages({
    mailboxId = null,
    folder = null,
    direction = null,
    status = null,
    search = null,
    limit = 50,
    cursor = null,
    // legacy helper used by early smoke
    mailbox = null,
  } = {}) {
    const accountId = this._c.accountId;
    if (mailbox && !mailboxId && this._useMailDataPlane()) {
      // Early MVP path: /{account}/mailboxes/{name}/messages
      const reqPath = `/${accountId}/mailboxes/${encodeURIComponent(mailbox)}/messages`;
      return this._c.dataPlaneRequest("mail", "GET", reqPath, { params: { limit } });
    }
    const params = { limit };
    if (mailboxId) params.mailbox_id = mailboxId;
    if (folder) params.folder = folder;
    if (direction) params.direction = direction;
    if (status) params.status = status;
    if (search) params.search = search;
    if (cursor) params.cursor = cursor;
    return this._mailRequest("GET", `accounts/${accountId}/mail/messages`, { params });
  }

  async getMessage(messageId) {
    const accountId = this._c.accountId;
    return this._mailRequest("GET", `accounts/${accountId}/mail/messages/${messageId}`);
  }

  async downloadAttachment(messageId, partId) {
    const accountId = this._c.accountId;
    return this._mailRequestBytes(
      "GET",
      `accounts/${accountId}/mail/messages/${messageId}/attachments/${partId}`
    );
  }
}

module.exports = { MailAPI };
