package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.List;
import java.util.Map;

public final class Functions {
    private final HomeCloud c;

    Functions(HomeCloud c) {
        this.c = c;
    }

    public List<FunctionInfo> list() {
        c.ensureAccountId();
        return Json.itemsOf(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/functions", true, null, null, null, null), FunctionInfo.class);
    }

    public JsonNode url(String name) {
        c.ensureAccountId();
        return Json.parse(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/functions/" + name + "/url", true, null, null, null, null));
    }

    public JsonNode enableUrl(String name, EnableUrlOptions opts) {
        if (opts == null) {
            opts = EnableUrlOptions.defaults();
        }
        int rate = opts.rateLimitPerMinute() == 0 ? 60 : opts.rateLimitPerMinute();
        c.ensureAccountId();
        return Json.parse(c.consoleJson(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/functions/" + name + "/url/enable",
                true,
                Map.of("public_url_enabled", opts.publicUrl(), "rate_limit_per_minute", rate),
                null, null, Transport.RetryMode.NEVER));
    }

    public JsonNode disableUrl(String name) {
        c.ensureAccountId();
        return Json.parse(c.consoleJson(
                "POST",
                "accounts/" + c.accountIdOrEmpty() + "/functions/" + name + "/url/disable",
                true, null, null, null, Transport.RetryMode.NEVER));
    }

    public JsonNode invoke(String name, Object payload) {
        c.requireAccessKey();
        c.ensureAccountId();
        if (payload == null) {
            payload = Map.of();
        }
        Transport.Spec spec = new Transport.Spec();
        spec.method = "POST";
        spec.url = Env.trimSlash(Env.functionUrl(name, c.apex())) + "/";
        spec.signPath = "/";
        spec.accountId = c.accountIdOrEmpty();
        spec.signed = true;
        spec.jsonBody = payload;
        spec.retry = Transport.RetryMode.NEVER;
        return Json.parse(Transport.doRequest(c, spec));
    }

    public JsonNode logs(String name) {
        c.ensureAccountId();
        return Json.parse(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/functions/" + name + "/invocations", true, null, null, null, null));
    }

    public JsonNode getInvocation(String name, String invocationId) {
        c.ensureAccountId();
        return Json.parse(c.consoleJson("GET", "accounts/" + c.accountIdOrEmpty() + "/functions/" + name + "/invocations/" + invocationId, true, null, null, null, null));
    }
}
