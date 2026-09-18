package com.homecloudlab.sdk;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Secrets {
    private final HomeCloud c;

    Secrets(HomeCloud c) {
        this.c = c;
    }

    public List<Secret> list() {
        c.ensureAccountId();
        return Json.itemsOf(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/secrets", true, null, null, null, null), Secret.class);
    }

    /** Data plane — secret metadata (no values). */
    public Secret get(String name) {
        c.requireAccessKey();
        c.ensureAccountId();
        String path = "/" + c.accountIdOrEmpty() + "/secrets/" + URLEncoder.encode(name, StandardCharsets.UTF_8);
        byte[] raw = c.dataPlaneJson("secrets", "GET", path, "", null, null, null);
        Secret sec = Json.decode(raw, Secret.class);
        if (sec == null) {
            return new Secret(name, null, null, null);
        }
        String n = sec.name() == null || sec.name().isEmpty() ? name : sec.name();
        return new Secret(n, sec.values(), sec.version(), sec.value());
    }

    /** Data plane — full secret values map. */
    public Secret getValue(String name) {
        return getValue(name, List.of());
    }

    /** Data plane — secret values, optionally filtered to ``keys`` (missing → 404). */
    public Secret getValue(String name, List<String> keys) {
        c.requireAccessKey();
        c.ensureAccountId();
        String path = "/" + c.accountIdOrEmpty() + "/secrets/" + URLEncoder.encode(name, StandardCharsets.UTF_8) + "/value";
        Map<String, String> query = keysQuery(keys);
        byte[] raw = c.dataPlaneJson("secrets", "GET", path, "", query.isEmpty() ? null : query, null, null);
        Secret sec = Json.decode(raw, Secret.class);
        if (sec == null) {
            return new Secret(name, Map.of(), null, null);
        }
        String n = sec.name() == null || sec.name().isEmpty() ? name : sec.name();
        return new Secret(n, sec.values(), sec.version(), sec.value());
    }

    /** Data plane — replace the entire values map. */
    public Secret putValue(String name, Map<String, String> values) {
        return putValue(name, values, false);
    }

    /**
     * Data plane — write values.
     *
     * @param merge false = replace entire map; true = upsert keys only
     */
    public Secret putValue(String name, Map<String, String> values, boolean merge) {
        c.requireAccessKey();
        c.ensureAccountId();
        if (values == null || values.isEmpty()) {
            throw new HomeCloudException("values must be a non-empty string map");
        }
        String path = "/" + c.accountIdOrEmpty() + "/secrets/" + URLEncoder.encode(name, StandardCharsets.UTF_8) + "/value";
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("values", values);
        if (merge) {
            body.put("mode", "merge");
        }
        byte[] raw = c.dataPlaneJson("secrets", "PUT", path, "", null, body, null);
        Secret sec = Json.decode(raw, Secret.class);
        if (sec == null) {
            return new Secret(name, values, null, null);
        }
        String n = sec.name() == null || sec.name().isEmpty() ? name : sec.name();
        return new Secret(n, sec.values() != null ? sec.values() : values, sec.version(), sec.value());
    }

    private static Map<String, String> keysQuery(List<String> keys) {
        if (keys == null || keys.isEmpty()) {
            return Map.of();
        }
        List<String> normalized = new ArrayList<>();
        for (String item : keys) {
            if (item == null) {
                continue;
            }
            for (String part : item.split(",")) {
                String key = part.trim();
                if (!key.isEmpty() && !normalized.contains(key)) {
                    normalized.add(key);
                }
            }
        }
        if (normalized.isEmpty()) {
            return Map.of();
        }
        return Map.of("keys", String.join(",", normalized));
    }
}
