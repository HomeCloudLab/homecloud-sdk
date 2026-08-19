package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Ir {
    private final HomeCloud c;

    Ir(HomeCloud c) {
        this.c = c;
    }

    public RegistryList list() {
        c.ensureAccountId();
        RegistryList list = Json.decode(
                c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/registry/repositories", true, null, null, null, null),
                RegistryList.class);
        return list == null ? new RegistryList(List.of()) : list;
    }

    public JsonNode create(String name, int keepLast) {
        c.ensureAccountId();
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("name", name);
        if (keepLast > 0) {
            body.put("keep_last", keepLast);
        }
        return Json.parse(c.consoleJson(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/registry/repositories",
                true, body, null, Transport.newIdempotencyKey(), Transport.RetryMode.IF_IDEMPOTENCY));
    }

    public JsonNode usage() {
        c.ensureAccountId();
        return Json.parse(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/registry/repositories/usage", true, null, null, null, null));
    }
}
