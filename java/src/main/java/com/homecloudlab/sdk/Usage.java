package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.Map;

public final class Usage {
    private final HomeCloud c;

    Usage(HomeCloud c) {
        this.c = c;
    }

    public JsonNode list(Map<String, String> params) {
        c.ensureAccountId();
        return Json.parse(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/usage", true, null, params, null, null));
    }
}
