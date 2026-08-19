package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.json.JsonMapper;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class Json {
    static final ObjectMapper MAPPER = JsonMapper.builder()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
            .build();

    private Json() {}

    static JsonNode parse(byte[] raw) {
        if (raw == null || raw.length == 0) {
            return MAPPER.missingNode();
        }
        try {
            return MAPPER.readTree(raw);
        } catch (Exception e) {
            throw new HomeCloudException("Invalid JSON response", e);
        }
    }

    static <T> T decode(byte[] raw, Class<T> type) {
        if (raw == null || raw.length == 0) {
            try {
                return type.getDeclaredConstructor().newInstance();
            } catch (Exception e) {
                return null;
            }
        }
        try {
            return MAPPER.readValue(raw, type);
        } catch (Exception e) {
            throw new HomeCloudException("Invalid JSON response", e);
        }
    }

    static <T> List<T> itemsOf(byte[] raw, Class<T> itemType) {
        if (raw == null || raw.length == 0) {
            return List.of();
        }
        try {
            JsonNode node = MAPPER.readTree(raw);
            JsonNode items = node.get("items");
            if (items != null && items.isArray()) {
                return MAPPER.convertValue(items, MAPPER.getTypeFactory().constructCollectionType(List.class, itemType));
            }
            if (node.isArray()) {
                return MAPPER.convertValue(node, MAPPER.getTypeFactory().constructCollectionType(List.class, itemType));
            }
            return List.of();
        } catch (Exception e) {
            throw new HomeCloudException("Invalid JSON response", e);
        }
    }

    static Map<String, Object> asMap(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return Map.of();
        }
        return MAPPER.convertValue(node, MAPPER.getTypeFactory().constructMapType(LinkedHashMap.class, String.class, Object.class));
    }

    static Object toDetail(byte[] raw) {
        if (raw == null || raw.length == 0) {
            return null;
        }
        try {
            JsonNode node = MAPPER.readTree(raw);
            if (node.has("detail")) {
                return MAPPER.convertValue(node.get("detail"), Object.class);
            }
            return MAPPER.convertValue(node, Object.class);
        } catch (Exception e) {
            return new String(raw, java.nio.charset.StandardCharsets.UTF_8);
        }
    }

    static Map<String, String> stringMap(Object raw) {
        Map<String, String> out = new LinkedHashMap<>();
        if (!(raw instanceof Map<?, ?> m)) {
            return out;
        }
        for (var e : m.entrySet()) {
            out.put(String.valueOf(e.getKey()), Errors.stringify(e.getValue()));
        }
        return out;
    }

    static List<Object> asList(Object body) {
        if (body instanceof List<?> list) {
            return new ArrayList<>(list);
        }
        try {
            byte[] raw = MAPPER.writeValueAsBytes(body);
            if (raw.length == 0 || raw[0] != '[') {
                return null;
            }
            return MAPPER.readValue(raw, MAPPER.getTypeFactory().constructCollectionType(List.class, Object.class));
        } catch (Exception e) {
            return null;
        }
    }
}

