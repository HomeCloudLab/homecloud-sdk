package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Objects;

/**
 * Account Tasks — management plane (console-parity).
 * Auth: user JWT or user-bound Access Key SigV1.
 */
public final class Tasks {
    private final HomeCloud c;
    private String actorUserId;
    private List<Map<String, Object>> peopleCache;

    Tasks(HomeCloud c) {
        this.c = c;
    }

    private byte[] request(String method, String path, Object jsonBody, Map<String, String> query) {
        c.ensureAccountId();
        if (c.hasAccessKey()) {
            return c.consoleSignedJson(method, path, c.accountIdOrEmpty(), jsonBody, query, null);
        }
        return c.consoleJson(method, path, true, jsonBody, query, null, null);
    }

    private Map<String, Object> asMap(byte[] raw) {
        return Json.asMap(Json.parse(raw));
    }

    private List<Map<String, Object>> asItems(byte[] raw) {
        JsonNode node = Json.parse(raw);
        JsonNode items = node.get("items");
        List<Map<String, Object>> out = new ArrayList<>();
        if (items != null && items.isArray()) {
            for (JsonNode item : items) {
                out.add(Json.asMap(item));
            }
        }
        return out;
    }

    private static String enc(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8).replace("+", "%20");
    }

    private static boolean looksLikeUuid(String value) {
        if (value == null || value.length() != 36) {
            return false;
        }
        for (int i = 0; i < value.length(); i++) {
            char r = value.charAt(i);
            if (i == 8 || i == 13 || i == 18 || i == 23) {
                if (r != '-') {
                    return false;
                }
            } else if (!((r >= '0' && r <= '9') || (r >= 'a' && r <= 'f') || (r >= 'A' && r <= 'F'))) {
                return false;
            }
        }
        return true;
    }

    public Map<String, Object> actor() {
        c.ensureAccountId();
        byte[] raw;
        if (c.hasAccessKey()) {
            raw = c.consoleSignedJson("GET", "access-key/whoami", c.accountIdOrEmpty(), null, null, null);
        } else {
            raw = c.consoleJson("GET", "me", true, null, null, null, null);
        }
        return asMap(raw);
    }

    public String actorUserId() {
        if (actorUserId != null && !actorUserId.isEmpty()) {
            return actorUserId;
        }
        Map<String, Object> info = actor();
        Object uid = info.get("id");
        if (uid == null) {
            uid = info.get("principal_id");
        }
        if (uid == null || String.valueOf(uid).isBlank()) {
            throw new HomeCloudException(
                    "Could not resolve current user id — use login or a user-bound Access Key");
        }
        actorUserId = String.valueOf(uid);
        return actorUserId;
    }

    public List<Map<String, Object>> people() {
        if (peopleCache != null) {
            return peopleCache;
        }
        peopleCache = asItems(request("GET", "accounts/" + c.accountIdOrEmpty() + "/tasks/people", null, null));
        return peopleCache;
    }

    public String resolveUser(String ref) {
        String raw = Objects.requireNonNullElse(ref, "").trim().replaceAll("^@+", "");
        if (raw.isEmpty()) {
            throw new HomeCloudException("empty user reference");
        }
        if ("me".equalsIgnoreCase(raw)) {
            return actorUserId();
        }
        if (looksLikeUuid(raw)) {
            return raw;
        }
        String lower = raw.toLowerCase(Locale.ROOT);
        for (Map<String, Object> p : people()) {
            Object username = p.get("username");
            if (username != null && String.valueOf(username).toLowerCase(Locale.ROOT).equals(lower)) {
                return String.valueOf(p.get("id"));
            }
        }
        throw new HomeCloudException("Unknown user: " + ref);
    }

    public List<Map<String, Object>> list(Map<String, String> filters) {
        Map<String, String> params = new LinkedHashMap<>();
        params.put("archived", "false");
        if (filters != null) {
            for (var e : filters.entrySet()) {
                if (e.getValue() != null && !e.getValue().isEmpty()) {
                    params.put(e.getKey(), e.getValue());
                }
            }
        }
        if (!params.containsKey("archived")) {
            params.put("archived", "false");
        }
        return asItems(request("GET", "accounts/" + c.accountIdOrEmpty() + "/tasks/items", null, params));
    }

    public List<Map<String, Object>> search(String query) {
        Map<String, String> filters = new LinkedHashMap<>();
        if (query != null && !query.isEmpty()) {
            filters.put("q", query);
        }
        return list(filters);
    }

    public Map<String, Object> get(String key) {
        return asMap(request(
                "GET",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key),
                null,
                null));
    }

    public Map<String, Object> create(String title, Map<String, Object> opts) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("title", title);
        body.put("type", "task");
        if (opts != null) {
            Object type = opts.get("type");
            if (type != null) {
                body.put("type", type);
            }
            putIf(body, opts, "description");
            putIf(body, opts, "description_format");
            putIf(body, opts, "due_at");
            putIf(body, opts, "project_id");
            putIf(body, opts, "priority");
            putIf(body, opts, "severity");
            putIf(body, opts, "services");
            putIf(body, opts, "label_names");
            Object assignees = opts.get("assignees");
            if (assignees instanceof List<?> list) {
                List<String> ids = new ArrayList<>();
                for (Object a : list) {
                    ids.add(resolveUser(String.valueOf(a)));
                }
                body.put("assignee_user_ids", ids);
            }
            Object assigneeUserId = opts.get("assignee_user_id");
            if (assigneeUserId != null) {
                String s = String.valueOf(assigneeUserId);
                body.put("assignee_user_id", looksLikeUuid(s) ? s : resolveUser(s));
            }
        }
        return asMap(request("POST", "accounts/" + c.accountIdOrEmpty() + "/tasks/items", body, null));
    }

    public Map<String, Object> update(String key, Map<String, Object> fields) {
        Map<String, Object> body = new LinkedHashMap<>();
        if (fields != null) {
            body.putAll(fields);
        }
        Object assignees = body.remove("assignees");
        if (assignees instanceof List<?> list) {
            List<String> ids = new ArrayList<>();
            for (Object a : list) {
                ids.add(resolveUser(String.valueOf(a)));
            }
            body.put("assignee_user_ids", ids);
        }
        return asMap(request(
                "PATCH",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key),
                body,
                null));
    }

    public Map<String, Object> assign(String key, String... users) {
        if (users == null || users.length == 0) {
            throw new HomeCloudException("assign requires at least one user");
        }
        return update(key, Map.of("assignees", List.of(users)));
    }

    public Map<String, Object> assignMe(String key) {
        return assignMe(key, null);
    }

    public Map<String, Object> assignMe(String key, String status) {
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("assignees", List.of("me"));
        if (status != null && !status.isEmpty()) {
            fields.put("status", status);
        }
        return update(key, fields);
    }

    public Map<String, Object> unassign(String key) {
        return update(key, Map.of("clear_assignee", true));
    }

    public Map<String, Object> archive(String key) {
        return archive(key, false);
    }

    public Map<String, Object> archive(String key, boolean cancel) {
        return asMap(request(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/archive",
                Map.of("cancel", cancel),
                null));
    }

    public Map<String, Object> restore(String key) {
        return asMap(request(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/restore",
                Map.of(),
                null));
    }

    public void delete(String key) {
        request("DELETE", "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key), null, null);
    }

    public List<Map<String, Object>> activity(String key) {
        return asItems(request(
                "GET",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/activity",
                null,
                null));
    }

    public Map<String, Object> comment(String key, String body) {
        return comment(key, body, null);
    }

    public Map<String, Object> comment(String key, String body, String quoteCommentId) {
        Map<String, Object> json = new LinkedHashMap<>();
        json.put("body", body);
        if (quoteCommentId != null && !quoteCommentId.isEmpty()) {
            json.put("quote_comment_id", quoteCommentId);
        }
        return asMap(request(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/comments",
                json,
                null));
    }

    public Map<String, Object> commentUpdate(String key, String commentId, String body) {
        return asMap(request(
                "PATCH",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/comments/" + enc(commentId),
                Map.of("body", body),
                null));
    }

    public Map<String, Object> commentDelete(String key, String commentId) {
        return asMap(request(
                "DELETE",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/comments/" + enc(commentId),
                null,
                null));
    }

    public Map<String, Object> watch(String key) {
        return watch(key, "me");
    }

    public Map<String, Object> watch(String key, String user) {
        String userId = resolveUser(user == null || user.isEmpty() ? "me" : user);
        return asMap(request(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/watchers",
                Map.of("user_id", userId),
                null));
    }

    public Map<String, Object> unwatch(String key) {
        return unwatch(key, "me");
    }

    public Map<String, Object> unwatch(String key, String user) {
        String userId = resolveUser(user == null || user.isEmpty() ? "me" : user);
        return asMap(request(
                "DELETE",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/watchers/" + enc(userId),
                null,
                null));
    }

    public Map<String, Object> addLabel(String key, String name) {
        return addLabel(key, name, null);
    }

    public Map<String, Object> addLabel(String key, String name, String color) {
        Map<String, Object> json = new LinkedHashMap<>();
        json.put("name", name);
        if (color != null && !color.isEmpty()) {
            json.put("color", color);
        }
        return asMap(request(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/labels",
                json,
                null));
    }

    public Map<String, Object> removeLabel(String key, String labelId) {
        return asMap(request(
                "DELETE",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/labels/" + enc(labelId),
                null,
                null));
    }

    public List<Map<String, Object>> labels() {
        return labels(false);
    }

    public List<Map<String, Object>> labels(boolean includeArchived) {
        Map<String, String> q = Map.of("include_archived", includeArchived ? "true" : "false");
        return asItems(request("GET", "accounts/" + c.accountIdOrEmpty() + "/tasks/labels", null, q));
    }

    public Map<String, Object> createLabel(String name) {
        return createLabel(name, "#64748b");
    }

    public Map<String, Object> createLabel(String name, String color) {
        Map<String, Object> json = new LinkedHashMap<>();
        json.put("name", name);
        json.put("color", color == null || color.isEmpty() ? "#64748b" : color);
        return asMap(request("POST", "accounts/" + c.accountIdOrEmpty() + "/tasks/labels", json, null));
    }

    public Map<String, Object> linkResource(String key, String resourceType, String resourceId, String resourceRef) {
        Map<String, Object> json = new LinkedHashMap<>();
        json.put("resource_type", resourceType);
        json.put("resource_id", resourceId);
        json.put("resource_ref", resourceRef == null ? "" : resourceRef);
        return asMap(request(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/resources",
                json,
                null));
    }

    public Map<String, Object> unlinkResource(String key, String linkId) {
        return asMap(request(
                "DELETE",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/resources/" + enc(linkId),
                null,
                null));
    }

    public Map<String, Object> createShare(String key) {
        return createShare(key, "never", null, false);
    }

    public Map<String, Object> createShare(String key, String expiresIn, String label, boolean includeDiscussion) {
        Map<String, Object> json = new LinkedHashMap<>();
        json.put("expires_in", expiresIn == null || expiresIn.isEmpty() ? "never" : expiresIn);
        json.put("include_discussion", includeDiscussion);
        if (label != null && !label.isEmpty()) {
            json.put("label", label);
        }
        return asMap(request(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/shares",
                json,
                null));
    }

    public List<Map<String, Object>> listShares(String key) {
        return asItems(request(
                "GET",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/shares",
                null,
                null));
    }

    public void revokeShare(String key, String shareId) {
        request(
                "DELETE",
                "accounts/" + c.accountIdOrEmpty() + "/tasks/items/" + enc(key) + "/shares/" + enc(shareId),
                null,
                null);
    }

    private static void putIf(Map<String, Object> body, Map<String, Object> opts, String key) {
        Object v = opts.get(key);
        if (v != null) {
            body.put(key, v);
        }
    }
}
