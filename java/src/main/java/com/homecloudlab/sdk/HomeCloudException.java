package com.homecloudlab.sdk;

/** Base unchecked HomeCloud SDK error. */
public class HomeCloudException extends RuntimeException {
    private final int statusCode;
    private final Object detail;

    public HomeCloudException(String message) {
        this(message, 0, null, null);
    }

    public HomeCloudException(String message, Throwable cause) {
        super(message, cause);
        this.statusCode = 0;
        this.detail = null;
    }

    HomeCloudException(String message, int statusCode, Object detail, Throwable cause) {
        super(message, cause);
        this.statusCode = statusCode;
        this.detail = detail;
    }

    public int getStatusCode() {
        return statusCode;
    }

    public Object getDetail() {
        return detail;
    }

    @SuppressWarnings("unchecked")
    public String getErrorCode() {
        Object payload = errorPayload();
        if (payload instanceof java.util.Map<?, ?> map) {
            Object code = map.get("code");
            return code == null ? "" : String.valueOf(code);
        }
        return "";
    }

    Object errorPayload() {
        if (!(detail instanceof java.util.Map<?, ?> d)) {
            return null;
        }
        Object errObj = d.get("error");
        if (errObj instanceof java.util.Map<?, ?> err) {
            Object code = err.get("code");
            if (code != null && !String.valueOf(code).isBlank()) {
                Object details = err.get("details");
                if (!(details instanceof java.util.Map)) {
                    details = java.util.Map.of();
                }
                Object msgObj = err.get("message");
                String msg = msgObj == null ? String.valueOf(code) : String.valueOf(msgObj);
                java.util.Map<String, Object> out = new java.util.LinkedHashMap<>();
                out.put("code", String.valueOf(code));
                out.put("message", msg);
                out.put("details", details);
                return out;
            }
        }
        Object code = d.get("code");
        if (code != null && !String.valueOf(code).isBlank()) {
            java.util.Map<String, Object> details = new java.util.LinkedHashMap<>();
            for (var e : d.entrySet()) {
                String k = String.valueOf(e.getKey());
                if (!"code".equals(k) && !"message".equals(k)) {
                    details.put(k, e.getValue());
                }
            }
            String msg = d.get("message") == null ? String.valueOf(code) : String.valueOf(d.get("message"));
            return java.util.Map.of("code", String.valueOf(code), "message", msg, "details", details);
        }
        return null;
    }
}
