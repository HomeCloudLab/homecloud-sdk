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
        String path = "accounts/" + c.accountIdOrEmpty() + "/queues";
        byte[] raw;
        if (c.hasAccessKey()) {
            raw = c.consoleSignedJson("GET", path, c.accountIdOrEmpty(), null, q, null);
        } else {
            raw = c.consoleJson("GET", path, true, null, q, null, null);
        }
        return Json.itemsOf(raw, Queue.class);
    }

    public Queue get(String name) {
        c.ensureAccountId();
        String path =
                "accounts/"
                        + c.accountIdOrEmpty()
                        + "/queues/"
                        + URLEncoder.encode(name, StandardCharsets.UTF_8);
        byte[] raw;
        if (c.hasAccessKey()) {
            raw = c.consoleSignedJson("GET", path, c.accountIdOrEmpty(), null, null, null);
        } else {
            raw = c.consoleJson("GET", path, true, null, null, null, null);
        }
        return Json.decode(raw, Queue.class);
    }
}
