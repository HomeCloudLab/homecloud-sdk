package com.homecloudlab.sdk;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;

public final class Queues {
    private final HomeCloud c;

    Queues(HomeCloud c) {
        this.c = c;
    }

    public List<Queue> list() {
        return list(false);
    }

    public List<Queue> list(boolean live) {
        c.ensureAccountId();
        Map<String, String> q = live ? Map.of("live", "true") : null;
        return Json.itemsOf(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/queues", true, null, q, null, null), Queue.class);
    }

    public Queue get(String name) {
        c.ensureAccountId();
        byte[] raw = c.consoleJson(
                "GET",
                "accounts/" + c.accountIdOrEmpty() + "/queues/" + URLEncoder.encode(name, StandardCharsets.UTF_8),
                true, null, null, null, null);
        return Json.decode(raw, Queue.class);
    }
}
