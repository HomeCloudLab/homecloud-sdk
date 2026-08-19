package com.homecloudlab.sdk;

import java.time.Duration;
import java.util.Locale;
import java.util.Map;

final class Env {
    static final String DEFAULT_APEX = "holab.abrdns.com";
    static final String DEFAULT_PROFILE = "default";
    static final String WHOAMI_PATH = "/access-key/whoami";
    static final String WHOAMI_ACCOUNT_SENTINEL = "-";
    static final int MAX_RETRIES = 2;
    static final int MQ_BATCH_MAX = 10;
    static final Duration DEFAULT_REQUEST_TIMEOUT = Duration.ofSeconds(30);
    static final Duration DEFAULT_CONNECT_TIMEOUT = Duration.ofSeconds(30);

    private final Map<String, String> override;

    Env(Map<String, String> override) {
        this.override = override;
    }

    String getenv(String name) {
        if (override != null && override.containsKey(name)) {
            String v = override.get(name);
            return v == null ? "" : v;
        }
        String v = System.getenv(name);
        return v == null ? "" : v;
    }

    String envFirst(String... names) {
        for (String name : names) {
            String v = getenv(name).trim();
            if (!v.isEmpty()) {
                return v;
            }
        }
        return "";
    }

    String profile() {
        return envFirst("HOMECLOUD_PROFILE", "HC_PROFILE");
    }

    String apex() {
        return trimSlash(envFirst("HOMECLOUD_APEX", "HC_APEX"));
    }

    String accountId() {
        return envFirst("HOMECLOUD_ACCOUNT_ID", "HC_ACCOUNT_ID");
    }

    String accessKeyId() {
        return envFirst("HOMECLOUD_ACCESS_KEY_ID", "HC_ACCESS_KEY_ID");
    }

    String secretAccessKey() {
        return envFirst("HOMECLOUD_SECRET_ACCESS_KEY", "HC_SECRET_ACCESS_KEY");
    }

    String configDir() {
        return envFirst("HOMECLOUD_CONFIG_DIR", "HC_CONFIG_DIR");
    }

    String credentialsFile() {
        return envFirst("HOMECLOUD_CREDENTIALS_FILE", "HC_CREDENTIALS_FILE");
    }

    String sessionFile() {
        return envFirst("HOMECLOUD_SESSION_FILE", "HC_SESSION_FILE");
    }

    String platformApex() {
        String v = apex();
        return v.isEmpty() ? DEFAULT_APEX : v;
    }

    static String consoleUrl(String apex) {
        return "https://console." + apex + "/api/v1";
    }

    static String soUrl(String apex) {
        return "https://so." + apex;
    }

    static String mqUrl(String apex) {
        return "https://mq." + apex;
    }

    static String secretsUrl(String apex) {
        return "https://secrets." + apex;
    }

    static String mailApiUrl(String apex) {
        return "https://mailapi." + apex;
    }

    static String functionUrl(String name, String apex) {
        return "https://" + name.trim().toLowerCase(Locale.ROOT) + ".func." + apex;
    }

    static String trimSlash(String s) {
        if (s == null) {
            return "";
        }
        String t = s.trim();
        while (t.endsWith("/")) {
            t = t.substring(0, t.length() - 1);
        }
        return t;
    }

    static String firstNonEmpty(String... vals) {
        for (String v : vals) {
            if (v != null && !v.isBlank()) {
                return v.trim();
            }
        }
        return "";
    }
}
