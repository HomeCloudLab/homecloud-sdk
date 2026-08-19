package com.homecloudlab.sdk;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

final class MqBatch {
    private MqBatch() {}

    static String entryBodyStr(Object value) {
        if (value instanceof String s) {
            if (s.isEmpty()) {
                throw new HomeCloudException("mq.send batch entry body must be non-empty");
            }
            return s;
        }
        try {
            return Json.MAPPER.writeValueAsString(value);
        } catch (Exception e) {
            throw new HomeCloudException("Invalid MQ body", e);
        }
    }

    static List<Map<String, Object>> buildEntries(List<Object> items) {
        if (items == null || items.size() < 1 || items.size() > Env.MQ_BATCH_MAX) {
            throw new HomeCloudException("mq.send batch requires 1–" + Env.MQ_BATCH_MAX + " messages");
        }
        List<Map<String, Object>> entries = new ArrayList<>();
        Set<String> seen = new LinkedHashSet<>();
        for (int index = 0; index < items.size(); index++) {
            Object item = items.get(index);
            Map<String, Object> entry = null;
            if (item instanceof Map<?, ?> m && m.get("body") instanceof String body) {
                if (body.isEmpty()) {
                    throw new HomeCloudException("mq.send batch entry body must be non-empty");
                }
                String id = m.get("id") != null ? String.valueOf(m.get("id")) : Integer.toString(index);
                entry = new LinkedHashMap<>();
                entry.put("id", id);
                entry.put("body", body);
                if (m.get("headers") != null) {
                    entry.put("headers", m.get("headers"));
                }
            }
            if (entry == null) {
                entry = new LinkedHashMap<>();
                entry.put("id", Integer.toString(index));
                entry.put("body", entryBodyStr(item));
            }
            String id = String.valueOf(entry.get("id"));
            if (!seen.add(id)) {
                throw new HomeCloudException("mq.send batch entry ids must be unique");
            }
            entries.add(entry);
        }
        return entries;
    }
}
