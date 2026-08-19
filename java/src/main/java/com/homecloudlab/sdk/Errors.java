package com.homecloudlab.sdk;

import java.net.URI;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class Errors {
    private Errors() {}

    static HomeCloudException fromStatus(int statusCode, Object detail, String rawUrl, Duration retryAfter) {
        String apiMsg = detailMessage(detail);
        String resourceType = "";
        String resource = "";
        String hintMsg = "";
        if (rawUrl != null && !rawUrl.isBlank()) {
            String[] hint = resourceHint(rawUrl);
            resourceType = hint[0];
            resource = hint[1];
            hintMsg = hint[2];
        }
        return switch (statusCode) {
            case 400 -> new BadRequestException(first(apiMsg, "Bad request"), statusCode, detail);
            case 401 -> new UnauthorizedException(first(apiMsg, "Unauthorized — check Access Key or console session"), statusCode, detail);
            case 403 -> new PermissionDeniedException(first(apiMsg, "Permission denied"), statusCode, detail);
            case 404 -> {
                String message = first(hintMsg, first(apiMsg, "Resource not found"));
                if (!hintMsg.isEmpty() && !apiMsg.isEmpty() && !hintMsg.contains(apiMsg)) {
                    message = hintMsg + " (" + apiMsg + ")";
                }
                yield new NotFoundException(message, statusCode, detail, resourceType, resource);
            }
            case 409 -> new ConflictException(first(apiMsg, "Conflict"), statusCode, detail);
            case 429 -> new RateLimitException(first(apiMsg, "Rate limit exceeded"), statusCode, detail, retryAfter);
            case 502, 503, 504 -> new ServiceUnavailableException(
                    first(apiMsg, "Service unavailable (" + statusCode + ")"), statusCode, detail);
            default -> new ApiException(first(apiMsg, "Request failed (" + statusCode + ")"), statusCode, detail);
        };
    }

    static HomeCloudException fromStatus(int statusCode, Object detail, String rawUrl) {
        return fromStatus(statusCode, detail, rawUrl, null);
    }

    static String detailMessage(Object detail) {
        if (detail == null) {
            return "";
        }
        if (detail instanceof String s) {
            return s.trim();
        }
        if (detail instanceof Map<?, ?> d) {
            Object errObj = d.get("error");
            if (errObj instanceof Map<?, ?> err) {
                String msg = stringify(err.get("message"));
                if (!msg.isEmpty()) {
                    return msg;
                }
                String code = stringify(err.get("code"));
                if (!code.isEmpty()) {
                    return code;
                }
            }
            String msg = stringify(d.get("message"));
            if (!msg.isEmpty()) {
                return msg;
            }
            return stringify(d.get("code"));
        }
        if (detail instanceof List<?> list) {
            List<String> parts = new ArrayList<>();
            for (int i = 0; i < list.size() && i < 3; i++) {
                Object item = list.get(i);
                if (item instanceof Map<?, ?> m) {
                    String msg = stringify(m.get("msg"));
                    if (!msg.isEmpty()) {
                        parts.add(msg);
                        continue;
                    }
                }
                parts.add(String.valueOf(item));
            }
            return String.join("; ", parts);
        }
        return "";
    }

    static String stringify(Object v) {
        if (v == null) {
            return "";
        }
        if (v instanceof Double d && d == d.longValue()) {
            return Long.toString(d.longValue());
        }
        String s = String.valueOf(v);
        return "<nil>".equals(s) ? "" : s;
    }

    static String[] resourceHint(String rawUrl) {
        URI u;
        try {
            u = URI.create(rawUrl);
        } catch (IllegalArgumentException e) {
            return new String[] {"", "", ""};
        }
        String path = u.getPath() == null ? "" : u.getPath();
        try {
            path = java.net.URLDecoder.decode(path, java.nio.charset.StandardCharsets.UTF_8);
        } catch (Exception ignored) {
            // keep encoded path
        }
        List<String> parts = new ArrayList<>();
        for (String p : path.split("/")) {
            if (!p.isEmpty()) {
                parts.add(p);
            }
        }
        if (parts.size() >= 3) {
            String name = parts.get(1);
            String kind = parts.get(2);
            if ("objects".equals(kind)) {
                List<String> keyParts = new ArrayList<>(parts.subList(3, parts.size()));
                while (!keyParts.isEmpty()) {
                    String last = keyParts.get(keyParts.size() - 1);
                    if (List.of("metadata", "uri", "presigned", "tags").contains(last)) {
                        keyParts.remove(keyParts.size() - 1);
                        continue;
                    }
                    break;
                }
                for (int i = 0; i < keyParts.size(); i++) {
                    if ("multipart".equals(keyParts.get(i))) {
                        keyParts = keyParts.subList(0, i);
                        break;
                    }
                }
                String key = String.join("/", keyParts);
                if (!key.isEmpty()) {
                    return new String[] {
                            "object",
                            name + "/" + key,
                            "Object not found: bucket=\"" + name + "\" key=\"" + key + "\""
                    };
                }
                return new String[] {"bucket", name, "Bucket not found: \"" + name + "\""};
            }
            if ("messages".equals(kind)) {
                return new String[] {"queue", name, "Queue not found: \"" + name + "\""};
            }
        }
        String lower = path.toLowerCase(Locale.ROOT);
        if (lower.contains("storage/buckets")) {
            return new String[] {"bucket", "", "Bucket not found"};
        }
        if (lower.contains("/queues")) {
            return new String[] {"queue", "", "Queue not found"};
        }
        if (lower.contains("/secrets")) {
            return new String[] {"secret", "", "Secret not found"};
        }
        return new String[] {"", "", ""};
    }

    private static String first(String a, String b) {
        return a == null || a.isBlank() ? b : a;
    }
}
