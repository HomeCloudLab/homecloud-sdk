package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Message queue data plane. {@code send} is never retried automatically. */
public final class Mq {
    private final HomeCloud c;

    Mq(HomeCloud c) {
        this.c = c;
    }

    public JsonNode send(String queue, Object body) {
        return send(queue, body, SendOptions.none());
    }

    public JsonNode send(String queue, Object body, SendOptions opts) {
        c.requireAccessKey();
        c.ensureAccountId();
        List<Object> list = Json.asList(body);
        if (list != null) {
            if (opts != null && opts.headers() != null) {
                throw new HomeCloudException("headers= is only supported for single mq.send, not batch");
            }
            var entries = MqBatch.buildEntries(list);
            String path = "/" + c.accountIdOrEmpty() + "/" + queue + "/messages/batch";
            return Json.parse(c.dataPlaneJson("mq", "POST", path, "", null, Map.of("entries", entries), Transport.RetryMode.NEVER));
        }
        String bodyStr = MqBatch.entryBodyStr(body);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("body", bodyStr);
        if (opts != null && opts.headers() != null) {
            payload.put("headers", opts.headers());
        }
        String path = "/" + c.accountIdOrEmpty() + "/" + queue + "/messages";
        return Json.parse(c.dataPlaneJson("mq", "POST", path, "", null, payload, Transport.RetryMode.NEVER));
    }

    public List<Message> receive(String queue, ReceiveOptions opts) {
        return receive(queue, "/messages", opts);
    }

    public List<Message> receiveDlq(String queue, ReceiveOptions opts) {
        return receive(queue, "/dlq/messages", opts);
    }

    private List<Message> receive(String queue, String suffix, ReceiveOptions opts) {
        c.requireAccessKey();
        c.ensureAccountId();
        if (opts == null) {
            opts = ReceiveOptions.defaults();
        }
        int max = opts.maxMessages() <= 0 ? 1 : opts.maxMessages();
        int wait = opts.waitSeconds() == 0 ? 20 : opts.waitSeconds();
        Map<String, String> q = new LinkedHashMap<>();
        q.put("max_messages", Integer.toString(max));
        q.put("wait_seconds", Integer.toString(wait));
        if (opts.delete()) {
            q.put("delete", "true");
        }
        String path = "/" + c.accountIdOrEmpty() + "/" + queue + suffix;
        return Json.itemsOf(c.dataPlaneJson("mq", "GET", path, "", q, null, null), Message.class);
    }

    public void delete(String queue, long sequence) {
        c.ensureAccountId();
        String path = "/" + c.accountIdOrEmpty() + "/" + queue + "/messages/" + sequence;
        c.dataPlaneJson("mq", "DELETE", path, "", null, null, null);
    }

    public void deleteDlq(String queue, long sequence) {
        c.ensureAccountId();
        String path = "/" + c.accountIdOrEmpty() + "/" + queue + "/dlq/messages/" + sequence;
        c.dataPlaneJson("mq", "DELETE", path, "", null, null, null);
    }

    public void purge(String queue) {
        c.ensureAccountId();
        String path = "/" + c.accountIdOrEmpty() + "/" + queue + "/purge";
        c.dataPlaneJson("mq", "POST", path, "", null, null, Transport.RetryMode.NEVER);
    }

    public void purgeDlq(String queue) {
        c.ensureAccountId();
        String path = "/" + c.accountIdOrEmpty() + "/" + queue + "/dlq/purge";
        c.dataPlaneJson("mq", "POST", path, "", null, null, Transport.RetryMode.NEVER);
    }
}
