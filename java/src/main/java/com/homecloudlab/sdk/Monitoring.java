package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

public final class Monitoring {
    private final HomeCloud c;

    Monitoring(HomeCloud c) {
        this.c = c;
    }

    public JsonNode workspace() {
        c.ensureAccountId();
        return Json.parse(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/monitoring/workspace", true, null, null, null, null));
    }

    public JsonNode dashboards() {
        c.ensureAccountId();
        return Json.parse(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/monitoring/dashboards", true, null, null, null, null));
    }
}
