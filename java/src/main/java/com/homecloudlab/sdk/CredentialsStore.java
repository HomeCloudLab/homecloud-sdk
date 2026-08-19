package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

final class CredentialsStore {
    record ProfileConfig(String name, String apex, String defaultAccountId, String accessKeyId, String secretAccessKey) {}

    record CredentialsFile(int version, String defaultProfile, Map<String, ProfileConfig> profiles) {}

    record ProfileSession(String accessToken, String activeAccountId, String lastUsedAccountId) {
        ProfileSession() {
            this("", "", "");
        }
    }

    private CredentialsStore() {}

    static Path homecloudDir(Env env) {
        String override = env.configDir();
        if (!override.isEmpty()) {
            return expandHome(override);
        }
        return Path.of(System.getProperty("user.home"), ".homecloud");
    }

    static Path credentialsPath(Env env) {
        String override = env.credentialsFile();
        if (!override.isEmpty()) {
            return expandHome(override);
        }
        return homecloudDir(env).resolve("credentials");
    }

    static Path sessionPath(Env env) {
        String override = env.sessionFile();
        if (!override.isEmpty()) {
            return expandHome(override);
        }
        return homecloudDir(env).resolve("session");
    }

    static Path expandHome(String p) {
        if (p.startsWith("~/") || p.startsWith("~\\")) {
            return Path.of(System.getProperty("user.home"), p.substring(2));
        }
        return Path.of(p);
    }

    static CredentialsFile loadCredentialsFile(Path path, String fallbackApex) {
        try {
            byte[] raw = Files.readAllBytes(path);
            @SuppressWarnings("unchecked")
            Map<String, Object> data = Json.MAPPER.readValue(raw, Map.class);
            Map<String, Object> normalized = normalize(data);
            int version = jsonInt(normalized.get("version"), 2);
            String defaultProfile = jsonString(normalized.get("default_profile"), Env.DEFAULT_PROFILE);
            Map<String, ProfileConfig> profiles = new LinkedHashMap<>();
            Object pobj = normalized.get("profiles");
            if (pobj instanceof Map<?, ?> pm) {
                for (var e : pm.entrySet()) {
                    String name = String.valueOf(e.getKey());
                    if (e.getValue() instanceof Map<?, ?> pv) {
                        profiles.put(name, new ProfileConfig(
                                name,
                                jsonString(pv.get("apex"), fallbackApex),
                                jsonString(pv.get("default_account_id"), ""),
                                jsonString(pv.get("access_key_id"), ""),
                                jsonString(pv.get("secret_access_key"), "")
                        ));
                    }
                }
            }
            if (profiles.isEmpty()) {
                throw new HomeCloudException("No profiles found in credentials file");
            }
            return new CredentialsFile(version, defaultProfile, profiles);
        } catch (HomeCloudException e) {
            throw e;
        } catch (IOException e) {
            return null;
        }
    }

    static void saveCredentialsFile(CredentialsFile cf, Path path) {
        try {
            Files.createDirectories(path.getParent());
            Map<String, Object> profiles = new LinkedHashMap<>();
            for (var e : cf.profiles().entrySet()) {
                ProfileConfig p = e.getValue();
                profiles.put(e.getKey(), Map.of(
                        "access_key_id", p.accessKeyId(),
                        "secret_access_key", p.secretAccessKey()
                ));
            }
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("version", cf.version());
            payload.put("default_profile", cf.defaultProfile());
            payload.put("profiles", profiles);
            Files.writeString(path, Json.MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(payload) + "\n");
        } catch (IOException e) {
            throw new HomeCloudException("Failed to write credentials file", e);
        }
    }

    static Map<String, ProfileSession> loadSessionFile(Path path) {
        Map<String, ProfileSession> out = new LinkedHashMap<>();
        try {
            JsonNode root = Json.MAPPER.readTree(Files.readAllBytes(path));
            JsonNode profiles = root.get("profiles");
            if (profiles == null || !profiles.isObject()) {
                return out;
            }
            profiles.fields().forEachRemaining(e -> {
                JsonNode p = e.getValue();
                out.put(e.getKey(), new ProfileSession(
                        text(p, "access_token"),
                        text(p, "active_account_id"),
                        text(p, "last_used_account_id")
                ));
            });
        } catch (IOException ignored) {
            return out;
        }
        return out;
    }

    static void saveSessionFile(Path path, Map<String, ProfileSession> profiles) {
        try {
            Files.createDirectories(path.getParent());
            Map<String, Object> payloadProfiles = new LinkedHashMap<>();
            for (var e : profiles.entrySet()) {
                ProfileSession p = e.getValue();
                if (blank(p.accessToken()) && blank(p.activeAccountId()) && blank(p.lastUsedAccountId())) {
                    continue;
                }
                Map<String, Object> entry = new LinkedHashMap<>();
                if (!blank(p.accessToken())) {
                    entry.put("access_token", p.accessToken());
                }
                if (!blank(p.activeAccountId())) {
                    entry.put("active_account_id", p.activeAccountId());
                }
                if (!blank(p.lastUsedAccountId())) {
                    entry.put("last_used_account_id", p.lastUsedAccountId());
                }
                payloadProfiles.put(e.getKey(), entry);
            }
            Map<String, Object> payload = Map.of("version", 1, "profiles", payloadProfiles);
            Files.writeString(path, Json.MAPPER.writerWithDefaultPrettyPrinter().writeValueAsString(payload) + "\n");
        } catch (IOException e) {
            throw new HomeCloudException("Failed to write session file", e);
        }
    }

    private static Map<String, Object> normalize(Map<String, Object> data) {
        if (data.containsKey("profiles")) {
            return data;
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("version", data.get("version"));
        out.put("default_profile", Env.DEFAULT_PROFILE);
        out.put("profiles", Map.of(Env.DEFAULT_PROFILE, data));
        return out;
    }

    private static String jsonString(Object v, String fallback) {
        if (!(v instanceof String s)) {
            return fallback;
        }
        s = s.trim();
        if (s.isEmpty()) {
            return fallback;
        }
        return Env.trimSlash(s);
    }

    private static int jsonInt(Object v, int fallback) {
        if (v instanceof Number n) {
            return n.intValue();
        }
        return fallback;
    }

    private static String text(JsonNode p, String field) {
        JsonNode n = p.get(field);
        return n == null || n.isNull() ? "" : n.asText("");
    }

    private static boolean blank(String s) {
        return s == null || s.isBlank();
    }
}
