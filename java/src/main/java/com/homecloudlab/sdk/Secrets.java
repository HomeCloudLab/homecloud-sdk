package com.homecloudlab.sdk;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
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

    /** Data plane — secret values map. */
    public Secret getValue(String name) {
        c.requireAccessKey();
        c.ensureAccountId();
        String path = "/" + c.accountIdOrEmpty() + "/secrets/" + URLEncoder.encode(name, StandardCharsets.UTF_8) + "/value";
        byte[] raw = c.dataPlaneJson("secrets", "GET", path, "", null, null, null);
        Secret sec = Json.decode(raw, Secret.class);
        if (sec == null) {
            return new Secret(name, Map.of(), null, null);
        }
        String n = sec.name() == null || sec.name().isEmpty() ? name : sec.name();
        return new Secret(n, sec.values(), sec.version(), sec.value());
    }

    /** Data plane — replace the entire values map. */
    public Secret putValue(String name, Map<String, String> values) {
        c.requireAccessKey();
        c.ensureAccountId();
        if (values == null || values.isEmpty()) {
            throw new HomeCloudException("values must be a non-empty string map");
        }
        String path = "/" + c.accountIdOrEmpty() + "/secrets/" + URLEncoder.encode(name, StandardCharsets.UTF_8) + "/value";
        byte[] raw = c.dataPlaneJson("secrets", "PUT", path, "", null, Map.of("values", values), null);
        Secret sec = Json.decode(raw, Secret.class);
        if (sec == null) {
            return new Secret(name, values, null, null);
        }
        String n = sec.name() == null || sec.name().isEmpty() ? name : sec.name();
        return new Secret(n, sec.values() != null ? sec.values() : values, sec.version(), sec.value());
    }
}
