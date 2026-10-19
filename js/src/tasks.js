"use strict";

const { HomeCloudError } = require("./errors");

function looksLikeUuid(value) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
    String(value || "")
  );
}

class TasksAPI {
  constructor(client) {
    this._c = client;
    this._actorUserId = null;
    this._peopleCache = null;
  }

  async _request(method, path, { json, params } = {}) {
    await this._c.ensureAccountId();
    if (this._c.hasAccessKey) {
      return this._c.consoleSignedRequest(method, path, { json, params });
    }
    this._c.requireConsole();
    return this._c.consoleRequest(method, path, { json, params });
  }

  async actor() {
    await this._c.ensureAccountId();
    if (this._c.hasAccessKey) {
      return this._c.consoleSignedRequest("GET", "access-key/whoami");
    }
    this._c.requireConsole();
    return this._c.consoleRequest("GET", "me");
  }

  async actorUserId() {
    if (this._actorUserId) return this._actorUserId;
    const info = await this.actor();
    const uid = info.id || info.principal_id;
    if (!uid) {
      throw new HomeCloudError(
        "Could not resolve current user id — use login or a user-bound Access Key"
      );
    }
    this._actorUserId = String(uid);
    return this._actorUserId;
  }

  async people() {
    if (this._peopleCache) return this._peopleCache;
    const data = await this._request(
      "GET",
      `accounts/${this._c.accountId}/tasks/people`
    );
    this._peopleCache = data.items || [];
    return this._peopleCache;
  }

  async resolveUser(ref) {
    const raw = String(ref || "")
      .trim()
      .replace(/^@+/, "");
    if (!raw) throw new HomeCloudError("empty user reference");
    if (raw.toLowerCase() === "me") return this.actorUserId();
    if (looksLikeUuid(raw)) return raw;
    const people = await this.people();
    const match = people.find(
      (p) => String(p.username || "").toLowerCase() === raw.toLowerCase()
    );
    if (!match) throw new HomeCloudError(`Unknown user: ${ref}`);
    return String(match.id);
  }

  async list({
    type,
    status,
    assignee,
    watcher,
    label,
    projectId,
    q,
    due,
    archived = false,
  } = {}) {
    const params = { archived: archived ? "true" : "false" };
    if (type != null) params.type = type;
    if (status != null) params.status = status;
    if (assignee != null) params.assignee = assignee;
    if (watcher != null) params.watcher = watcher;
    if (label != null) params.label = label;
    if (projectId != null) params.project_id = projectId;
    if (q != null) params.q = q;
    if (due != null) params.due = due;
    const data = await this._request(
      "GET",
      `accounts/${this._c.accountId}/tasks/items`,
      { params }
    );
    return data.items || [];
  }

  async search(query = "", filters = {}) {
    return this.list({ ...filters, q: query || undefined });
  }

  async get(key) {
    return this._request(
      "GET",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}`
    );
  }

  async create(title, opts = {}) {
    const body = { title, type: opts.type || "task" };
    if (opts.description != null) body.description = opts.description;
    if (opts.descriptionFormat != null) body.description_format = opts.descriptionFormat;
    if (opts.assignees && opts.assignees.length) {
      body.assignee_user_ids = await Promise.all(
        opts.assignees.map((a) => this.resolveUser(a))
      );
    }
    if (opts.assigneeUserId != null) {
      body.assignee_user_id = looksLikeUuid(opts.assigneeUserId)
        ? opts.assigneeUserId
        : await this.resolveUser(opts.assigneeUserId);
    }
    if (opts.dueAt != null) body.due_at = opts.dueAt;
    if (opts.projectId != null) body.project_id = opts.projectId;
    if (opts.priority != null) body.priority = opts.priority;
    if (opts.severity != null) body.severity = opts.severity;
    if (opts.services != null) body.services = opts.services;
    if (opts.labelNames != null) body.label_names = opts.labelNames;
    return this._request("POST", `accounts/${this._c.accountId}/tasks/items`, {
      json: body,
    });
  }

  async update(key, fields = {}) {
    const body = { ...fields };
    if (body.assignees) {
      body.assignee_user_ids = await Promise.all(
        body.assignees.map((a) => this.resolveUser(a))
      );
      delete body.assignees;
    }
    return this._request(
      "PATCH",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}`,
      { json: body }
    );
  }

  async assign(key, ...users) {
    if (!users.length) throw new HomeCloudError("assign requires at least one user");
    return this.update(key, { assignees: users });
  }

  async assignMe(key, { status } = {}) {
    const fields = { assignees: ["me"] };
    if (status != null) fields.status = status;
    return this.update(key, fields);
  }

  async unassign(key) {
    return this.update(key, { clear_assignee: true });
  }

  async archive(key, { cancel = false } = {}) {
    return this._request(
      "POST",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/archive`,
      { json: { cancel } }
    );
  }

  async restore(key) {
    return this._request(
      "POST",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/restore`,
      { json: {} }
    );
  }

  async delete(key) {
    return this._request(
      "DELETE",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}`
    );
  }

  async activity(key) {
    const data = await this._request(
      "GET",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/activity`
    );
    return data.items || [];
  }

  async comment(key, body, { quoteCommentId } = {}) {
    const json = { body };
    if (quoteCommentId != null) json.quote_comment_id = quoteCommentId;
    return this._request(
      "POST",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/comments`,
      { json }
    );
  }

  async commentUpdate(key, commentId, body) {
    return this._request(
      "PATCH",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/comments/${encodeURIComponent(commentId)}`,
      { json: { body } }
    );
  }

  async commentDelete(key, commentId) {
    return this._request(
      "DELETE",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/comments/${encodeURIComponent(commentId)}`
    );
  }

  async watch(key, user = "me") {
    const userId = await this.resolveUser(user);
    return this._request(
      "POST",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/watchers`,
      { json: { user_id: userId } }
    );
  }

  async unwatch(key, user = "me") {
    const userId = await this.resolveUser(user);
    return this._request(
      "DELETE",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/watchers/${encodeURIComponent(userId)}`
    );
  }

  async addLabel(key, name, { color } = {}) {
    const json = { name };
    if (color != null) json.color = color;
    return this._request(
      "POST",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/labels`,
      { json }
    );
  }

  async removeLabel(key, labelId) {
    return this._request(
      "DELETE",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/labels/${encodeURIComponent(labelId)}`
    );
  }

  async labels({ includeArchived = false } = {}) {
    const data = await this._request(
      "GET",
      `accounts/${this._c.accountId}/tasks/labels`,
      { params: { include_archived: includeArchived ? "true" : "false" } }
    );
    return data.items || [];
  }

  async createLabel(name, { color = "#64748b" } = {}) {
    return this._request("POST", `accounts/${this._c.accountId}/tasks/labels`, {
      json: { name, color },
    });
  }

  async linkResource(key, { resourceType, resourceId, resourceRef = "" }) {
    return this._request(
      "POST",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/resources`,
      {
        json: {
          resource_type: resourceType,
          resource_id: resourceId,
          resource_ref: resourceRef,
        },
      }
    );
  }

  async unlinkResource(key, linkId) {
    return this._request(
      "DELETE",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/resources/${encodeURIComponent(linkId)}`
    );
  }

  async createShare(key, { expiresIn = "never", label, includeDiscussion = false } = {}) {
    const json = { expires_in: expiresIn, include_discussion: includeDiscussion };
    if (label != null) json.label = label;
    return this._request(
      "POST",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/shares`,
      { json }
    );
  }

  async listShares(key) {
    const data = await this._request(
      "GET",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/shares`
    );
    return data.items || [];
  }

  async revokeShare(key, shareId) {
    return this._request(
      "DELETE",
      `accounts/${this._c.accountId}/tasks/items/${encodeURIComponent(key)}/shares/${encodeURIComponent(shareId)}`
    );
  }
}

module.exports = { TasksAPI };
