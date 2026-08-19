package com.homecloudlab.sdk;

import java.util.List;

public final class Apps {
    private final HomeCloud c;

    Apps(HomeCloud c) {
        this.c = c;
    }

    public List<Application> list() {
        c.ensureAccountId();
        return Json.itemsOf(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/applications", true, null, null, null, null), Application.class);
    }
}
