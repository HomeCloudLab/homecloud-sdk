package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;

public final class Secrets {
    private final HomeCloud c;

    Secrets(HomeCloud c) {
        this.c = c;
    }

    public List<Secret> list() {
        c.ensureAccountId();
        return Json.itemsOf(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/secrets", true, null, null, null, null), Secret.class);
    }

    public Secret get(String name) {
        c.requireAccessKey();
        c.ensureAccountId();
        String path = "/" + c.accountIdOrEmpty() + "/secrets/" + URLEncoder.encode(name, StandardCharsets.UTF_8);
        byte[] raw = c.dataPlaneJson("secrets", "GET", path, "", null, null, null);
        Secret sec = Json.decode(raw, Secret.class);
        JsonNode node = Json.parse(raw);
        if (sec == null) {
            return new Secret(name, node, "");
        }
        String n = sec.name() == null || sec.name().isEmpty() ? name : sec.name();
        JsonNode value = sec.value();
        if (value == null || value.isNull() || value.isMissingNode()) {
            value = node;
        }
        return new Secret(n, value, sec.version());
    }
}
