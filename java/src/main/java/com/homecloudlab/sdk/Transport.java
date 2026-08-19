package com.homecloudlab.sdk;

import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ThreadLocalRandom;

final class Transport {
    enum RetryMode {
        IDEMPOTENT, UPLOAD, IF_IDEMPOTENCY, NEVER
    }

    static final class Spec {
        String method = "GET";
        String url = "";
        String signPath = "";
        String accountId = "";
        Map<String, String> headers = new LinkedHashMap<>();
        Object jsonBody;
        Map<String, String> query;
        String multipartKey = "";
        String multipartFile = "";
        String multipartName = "";
        byte[] multipartBytes;
        byte[] rawBody;
        String contentType = "";
        RetryMode retry = RetryMode.NEVER;
        String idempotencyKey = "";
        boolean stream;
        boolean signed;
        boolean bearer;
    }

    private Transport() {}

    static byte[] doRequest(HomeCloud client, Spec spec) {
        Duration timeout = spec.stream ? Duration.ZERO : client.requestTimeout();
        byte[] lastBody = null;
        HomeCloudException lastErr = null;
        for (int attempt = 0; attempt <= Env.MAX_RETRIES; attempt++) {
            Body built = buildBody(spec);
            URI uri = URI.create(spec.url);
            if (spec.query != null && !spec.query.isEmpty()) {
                uri = withQuery(uri, spec.query);
            }
            HttpRequest.Builder rb = HttpRequest.newBuilder(uri);
            if (!timeout.isZero() && !timeout.isNegative()) {
                rb.timeout(timeout);
            }
            rb.method(spec.method, built.publisher);
            if (!built.contentType.isEmpty()) {
                rb.header("Content-Type", built.contentType);
            }
            spec.headers.forEach(rb::header);
            if (spec.signed) {
                String account = spec.accountId.isEmpty() ? client.accountIdOrEmpty() : spec.accountId;
                Signing.signHeaders(
                        client.accessKeyId(),
                        client.secretAccessKey(),
                        spec.method,
                        spec.signPath,
                        account,
                        Instant.now(),
                        client.sessionToken()
                ).forEach(rb::header);
            }
            if (spec.bearer && !client.accessToken().isEmpty()) {
                rb.header("Authorization", "Bearer " + client.accessToken());
            }
            if (!spec.idempotencyKey.isEmpty()) {
                rb.header(Signing.HEADER_IDEMPOTENCY, spec.idempotencyKey);
            }
            rb.header("User-Agent", "homecloud-sdk-java/" + Version.VALUE);

            HttpResponse<byte[]> resp;
            try {
                resp = client.httpClient().send(rb.build(), HttpResponse.BodyHandlers.ofByteArray());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                throw new HomeCloudException("Request cancelled", e);
            } catch (Exception e) {
                lastErr = new HomeCloudException("Request failed: " + e.getMessage(), e);
                if (attempt == Env.MAX_RETRIES || !allowsRetry(spec) || Thread.currentThread().isInterrupted()) {
                    throw lastErr;
                }
                sleepBackoff(attempt);
                continue;
            }

            int code = resp.statusCode();
            if (retryableStatus(code) && attempt < Env.MAX_RETRIES && allowsRetry(spec)) {
                if (!built.replayable && spec.retry != RetryMode.UPLOAD) {
                    throw errorFromBody(code, resp.body(), resp.uri().toString(), retryAfter(resp));
                }
                lastErr = errorFromBody(code, resp.body(), resp.uri().toString(), retryAfter(resp));
                sleepBackoff(attempt);
                continue;
            }
            if ("DELETE".equalsIgnoreCase(spec.method) && code == 204) {
                return new byte[0];
            }
            if (code >= 400) {
                throw errorFromBody(code, resp.body(), resp.uri().toString(), retryAfter(resp));
            }
            return resp.body() == null ? new byte[0] : resp.body();
        }
        if (lastErr != null) {
            throw lastErr;
        }
        throw new HomeCloudException("Request failed");
    }

    private static Duration retryAfter(HttpResponse<?> resp) {
        return resp.headers().firstValue("Retry-After").map(v -> {
            try {
                return Duration.ofSeconds(Long.parseLong(v.trim()));
            } catch (NumberFormatException e) {
                return null;
            }
        }).orElse(null);
    }

    static boolean retryableStatus(int code) {
        return code == 502 || code == 503 || code == 504;
    }

    static boolean allowsRetry(Spec spec) {
        return switch (spec.retry) {
            case NEVER -> false;
            case IF_IDEMPOTENCY -> spec.idempotencyKey != null && !spec.idempotencyKey.isEmpty();
            case UPLOAD, IDEMPOTENT -> true;
        };
    }

    static RetryMode retryFromMethod(String method) {
        return switch (method.toUpperCase()) {
            case "GET", "HEAD", "PUT", "DELETE" -> RetryMode.IDEMPOTENT;
            default -> RetryMode.NEVER;
        };
    }

    static String newIdempotencyKey() {
        return UUID.randomUUID().toString().replace("-", "");
    }

    private static void sleepBackoff(int attempt) {
        long capMs = 8_000;
        long exp = 500L * (1L << Math.min(attempt, 10));
        long max = Math.min(capMs, exp);
        long delay = max <= 0 ? 0 : ThreadLocalRandom.current().nextLong(max + 1);
        try {
            Thread.sleep(delay);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new HomeCloudException("Request cancelled", e);
        }
    }

    private static HomeCloudException errorFromBody(int status, byte[] raw, String rawUrl, Duration retryAfter) {
        Object detail = Json.toDetail(raw);
        return Errors.fromStatus(status, detail, rawUrl, retryAfter);
    }

    private record Body(HttpRequest.BodyPublisher publisher, String contentType, boolean replayable) {}

    private static Body buildBody(Spec spec) {
        try {
            if ((spec.multipartFile != null && !spec.multipartFile.isEmpty()) || spec.multipartBytes != null) {
                String boundary = "----HomeCloud" + UUID.randomUUID().toString().replace("-", "");
                byte[] data = multipartBytes(spec, boundary);
                return new Body(HttpRequest.BodyPublishers.ofByteArray(data), "multipart/form-data; boundary=" + boundary, true);
            }
            if (spec.jsonBody != null) {
                byte[] raw = Json.MAPPER.writeValueAsBytes(spec.jsonBody);
                return new Body(HttpRequest.BodyPublishers.ofByteArray(raw), "application/json", true);
            }
            if (spec.rawBody != null) {
                return new Body(HttpRequest.BodyPublishers.ofByteArray(spec.rawBody), spec.contentType, false);
            }
            return new Body(HttpRequest.BodyPublishers.noBody(), spec.contentType, true);
        } catch (HomeCloudException e) {
            throw e;
        } catch (Exception e) {
            throw new HomeCloudException("Failed to build request body", e);
        }
    }

    private static byte[] multipartBytes(Spec spec, String boundary) throws Exception {
        String filename = spec.multipartName == null || spec.multipartName.isEmpty() ? "object" : spec.multipartName;
        byte[] fileBytes;
        if (spec.multipartBytes != null) {
            fileBytes = spec.multipartBytes;
        } else {
            Path p = Path.of(spec.multipartFile);
            if (!Files.isRegularFile(p)) {
                throw new HomeCloudException("File not found: " + spec.multipartFile);
            }
            fileBytes = Files.readAllBytes(p);
        }
        String CRLF = "\r\n";
        StringBuilder head = new StringBuilder();
        head.append("--").append(boundary).append(CRLF);
        head.append("Content-Disposition: form-data; name=\"key\"").append(CRLF).append(CRLF);
        head.append(spec.multipartKey).append(CRLF);
        head.append("--").append(boundary).append(CRLF);
        head.append("Content-Disposition: form-data; name=\"file\"; filename=\"").append(filename).append("\"").append(CRLF);
        head.append("Content-Type: application/octet-stream").append(CRLF).append(CRLF);
        byte[] header = head.toString().getBytes(StandardCharsets.UTF_8);
        byte[] tail = (CRLF + "--" + boundary + "--" + CRLF).getBytes(StandardCharsets.UTF_8);
        byte[] all = new byte[header.length + fileBytes.length + tail.length];
        System.arraycopy(header, 0, all, 0, header.length);
        System.arraycopy(fileBytes, 0, all, header.length, fileBytes.length);
        System.arraycopy(tail, 0, all, header.length + fileBytes.length, tail.length);
        return all;
    }

    private static URI withQuery(URI uri, Map<String, String> query) {
        StringBuilder q = new StringBuilder();
        for (var e : query.entrySet()) {
            if (!q.isEmpty()) {
                q.append('&');
            }
            q.append(URLEncoder.encode(e.getKey(), StandardCharsets.UTF_8));
            q.append('=');
            q.append(URLEncoder.encode(e.getValue() == null ? "" : e.getValue(), StandardCharsets.UTF_8));
        }
        String base = uri.getScheme() + "://" + uri.getAuthority() + uri.getRawPath();
        return URI.create(base + "?" + q);
    }
}
