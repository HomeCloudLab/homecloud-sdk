package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Account Diagrams — management plane (user JWT or user-bound Access Key SigV1). */
public final class Diagrams {
    private final HomeCloud c;

    Diagrams(HomeCloud c) {
        this.c = c;
    }

    private byte[] request(String method, String path, Object jsonBody) {
        c.ensureAccountId();
        if (c.hasAccessKey()) {
            return c.consoleSignedJson(method, path, c.accountIdOrEmpty(), jsonBody, null, null);
        }
        return c.consoleJson(method, path, true, jsonBody, null, null, null);
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

    public List<Map<String, Object>> list() {
        return asItems(request("GET", "accounts/" + c.accountIdOrEmpty() + "/diagrams", null));
    }

    public Map<String, Object> get(String diagramId) {
        return asMap(request("GET", "accounts/" + c.accountIdOrEmpty() + "/diagrams/" + enc(diagramId), null));
    }

    public Map<String, Object> create(String name) {
        return create(name, null, null);
    }

    public Map<String, Object> create(String name, String description, Map<String, Object> document) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("name", name);
        if (description != null) {
            body.put("description", description);
        }
        if (document != null) {
            body.put("document", document);
        }
        return asMap(request("POST", "accounts/" + c.accountIdOrEmpty() + "/diagrams", body));
    }

    public Map<String, Object> update(String diagramId, Map<String, Object> fields) {
        Map<String, Object> body = fields == null ? Map.of() : fields;
        return asMap(request(
                "PATCH",
                "accounts/" + c.accountIdOrEmpty() + "/diagrams/" + enc(diagramId),
                body));
    }
}
