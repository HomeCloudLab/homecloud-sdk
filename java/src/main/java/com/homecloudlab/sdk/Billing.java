package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.Map;

public final class Billing {
    private final HomeCloud c;

    Billing(HomeCloud c) {
        this.c = c;
    }

    private JsonNode get(String suffix, Map<String, String> params) {
        c.ensureAccountId();
        return Json.parse(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/billing" + suffix, true, null, params, null, null));
    }

    public JsonNode summary() {
        return get("/summary", null);
    }

    public JsonNode forecast(int horizon) {
        if (horizon <= 0) {
            horizon = 30;
        }
        return get("/forecast", Map.of("horizon", Integer.toString(horizon)));
    }

    public JsonNode invoices() {
        return get("/invoices", null);
    }
}
