package com.homecloudlab.sdk;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

final class SoPaths {
    private SoPaths() {}

    static String encodeObjectKeyPath(String key) {
        key = trimLeftSlash(key);
        String[] parts = key.split("/", -1);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < parts.length; i++) {
            if (i > 0) {
                sb.append('/');
            }
            sb.append(URLEncoder.encode(parts[i], StandardCharsets.UTF_8).replace("+", "%20"));
        }
        return sb.toString();
    }

    static String[] soObjectPaths(String accountId, String bucket, String objectKey) {
        String key = trimLeftSlash(objectKey);
        String signPath = "/" + accountId + "/" + bucket + "/objects/" + key;
        String urlPath = "/" + accountId + "/" + bucket + "/objects/" + encodeObjectKeyPath(key);
        return new String[] {signPath, urlPath};
    }

    static boolean isSoUri(String target) {
        String l = target == null ? "" : target.trim().toLowerCase(Locale.ROOT);
        return l.startsWith("so://") || l.startsWith("s3://");
    }

    static String[] parseSoUri(String target) {
        String text = target == null ? "" : target.trim();
        String lower = text.toLowerCase(Locale.ROOT);
        if (lower.startsWith("so://")) {
            text = text.substring(5);
        } else if (lower.startsWith("s3://")) {
            text = text.substring(5);
        }
        while (text.startsWith("/")) {
            text = text.substring(1);
        }
        while (text.endsWith("/")) {
            text = text.substring(0, text.length() - 1);
        }
        if (text.isEmpty()) {
            throw new HomeCloudException("URI must include a bucket name");
        }
        int slash = text.indexOf('/');
        if (slash < 0) {
            return new String[] {text, ""};
        }
        return new String[] {text.substring(0, slash), text.substring(slash + 1)};
    }

    static String syncJoinPrefix(String prefixClean, String relative) {
        String rel = trimLeftSlash(relative);
        if (prefixClean == null || prefixClean.isEmpty()) {
            return rel;
        }
        if (rel.isEmpty()) {
            return prefixClean;
        }
        return prefixClean + "/" + rel;
    }

    static String syncRelativeLocalPath(String key, String prefixClean) {
        if (prefixClean == null || prefixClean.isEmpty()) {
            return key;
        }
        if (key.equals(prefixClean)) {
            int i = key.lastIndexOf('/');
            return i >= 0 ? key.substring(i + 1) : key;
        }
        if (key.startsWith(prefixClean + "/")) {
            return key.substring(prefixClean.length() + 1);
        }
        return key;
    }

    static String trimLeftSlash(String key) {
        if (key == null) {
            return "";
        }
        int i = 0;
        while (i < key.length() && key.charAt(i) == '/') {
            i++;
        }
        return key.substring(i);
    }

    static String guessContentType(String name) {
        String ext = "";
        int dot = name.lastIndexOf('.');
        if (dot >= 0) {
            ext = name.substring(dot).toLowerCase(Locale.ROOT);
        }
        return switch (ext) {
            case ".mp4" -> "video/mp4";
            case ".json" -> "application/json";
            case ".txt" -> "text/plain";
            case ".png" -> "image/png";
            case ".jpg", ".jpeg" -> "image/jpeg";
            case ".gif" -> "image/gif";
            case ".webp" -> "image/webp";
            case ".pdf" -> "application/pdf";
            case ".html", ".htm" -> "text/html";
            case ".csv" -> "text/csv";
            case ".zip" -> "application/zip";
            default -> "application/octet-stream";
        };
    }
}
