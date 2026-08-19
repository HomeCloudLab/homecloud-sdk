package com.homecloudlab.sdk;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/**
 * SigV1 HMAC-SHA256. Canonical string: {@code {METHOD}\n{path}\n{timestamp}\n{account_id}}.
 */
public final class Signing {
    public static final String HEADER_ACCESS_KEY_ID = "X-Homecloud-Access-Key-Id";
    public static final String HEADER_DATE = "X-Homecloud-Date";
    public static final String HEADER_SIGNATURE = "X-Homecloud-Signature";
    public static final String HEADER_SESSION_TOKEN = "X-Homecloud-Session-Token";
    public static final String HEADER_IDEMPOTENCY = "Idempotency-Key";

    private static final DateTimeFormatter TS =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss'Z'").withZone(ZoneOffset.UTC);

    private Signing() {}

    public static String buildStringToSign(String method, String path, String timestamp, String accountId) {
        return method.toUpperCase(Locale.ROOT) + "\n" + path + "\n" + timestamp + "\n" + accountId;
    }

    public static String computeSignature(String secret, String stringToSign) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            byte[] raw = mac.doFinal(stringToSign.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(raw.length * 2);
            for (byte b : raw) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException | InvalidKeyException e) {
            throw new HomeCloudException("HMAC-SHA256 failed", e);
        }
    }

    public static String formatTimestamp(Instant instant) {
        return TS.format(instant.truncatedTo(ChronoUnit.SECONDS));
    }

    static Map<String, String> signHeaders(
            String accessKeyId,
            String secret,
            String method,
            String path,
            String accountId,
            Instant now,
            String sessionToken) {
        String ts = formatTimestamp(now);
        String sig = computeSignature(secret, buildStringToSign(method, path, ts, accountId));
        Map<String, String> h = new LinkedHashMap<>();
        h.put(HEADER_ACCESS_KEY_ID, accessKeyId);
        h.put(HEADER_DATE, ts);
        h.put(HEADER_SIGNATURE, sig);
        if (sessionToken != null && !sessionToken.isBlank()) {
            h.put(HEADER_SESSION_TOKEN, sessionToken);
        }
        return h;
    }
}
