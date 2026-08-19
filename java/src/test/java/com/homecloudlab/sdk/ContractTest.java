package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import org.junit.jupiter.api.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class SigningTest {
    @Test
    void sigV1Vectors() throws Exception {
        Path path = Path.of("..", "testdata", "contracts", "sigv1_vectors.json");
        JsonNode vectors = Json.MAPPER.readTree(Files.readAllBytes(path));
        assertTrue(vectors.size() > 0);
        for (JsonNode v : vectors) {
            String got = Signing.buildStringToSign(
                    v.get("method").asText(),
                    v.get("path").asText(),
                    v.get("timestamp").asText(),
                    v.get("account_id").asText());
            assertEquals(v.get("string_to_sign").asText(), got, v.get("name").asText());
            String sig = Signing.computeSignature(v.get("secret").asText(), got);
            assertEquals(v.get("signature").asText(), sig, v.get("name").asText());
            assertEquals(64, sig.length());
        }
    }

    @Test
    void formatTimestampNoMicros() {
        Instant t = Instant.parse("2026-08-17T12:00:00.123456Z");
        assertEquals("2026-08-17T12:00:00Z", Signing.formatTimestamp(t));
    }
}

class ErrorFromStatusTest {
    @Test
    void contract() throws Exception {
        Path path = Path.of("..", "testdata", "contracts", "error_from_status.json");
        JsonNode cases = Json.MAPPER.readTree(Files.readAllBytes(path));
        for (JsonNode tc : cases) {
            Object detail = Json.MAPPER.convertValue(tc.get("detail"), Object.class);
            HomeCloudException err = Errors.fromStatus(tc.get("status").asInt(), detail, tc.path("url").asText(""));
            String type = tc.get("type").asText();
            switch (type) {
                case "NotFoundError" -> {
                    assertTrue(err instanceof NotFoundException, type);
                    NotFoundException nf = (NotFoundException) err;
                    assertEquals(tc.path("resource_type").asText(), nf.getResourceType());
                    assertEquals(tc.path("resource").asText(), nf.getResource());
                    assertTrue(err instanceof ApiException);
                }
                case "UnauthorizedError" -> assertTrue(err instanceof UnauthorizedException);
                case "PermissionDeniedError" -> {
                    assertTrue(err instanceof PermissionDeniedException);
                    String code = tc.path("error_code").asText("");
                    if (!code.isEmpty()) {
                        assertEquals(code, err.getErrorCode());
                    }
                }
                case "BadRequestError" -> assertTrue(err instanceof BadRequestException);
                case "ConflictError" -> assertTrue(err instanceof ConflictException);
                case "RateLimitError" -> assertTrue(err instanceof RateLimitException);
                case "ServiceUnavailableError" -> assertTrue(err instanceof ServiceUnavailableException);
                default -> throw new AssertionError("unknown type " + type);
            }
        }
    }
}

class MqBatchTest {
    @Test
    void entries() {
        var entries = MqBatch.buildEntries(List.of("a", Map.of("x", 1)));
        assertEquals(2, entries.size());
        assertEquals("a", entries.get(0).get("body"));
    }

    @Test
    void limits() {
        assertThrows(HomeCloudException.class, () -> MqBatch.buildEntries(List.of()));
        assertThrows(HomeCloudException.class, () -> MqBatch.buildEntries(List.of("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11")));
    }

    @Test
    void uniqueIds() {
        assertThrows(HomeCloudException.class, () -> MqBatch.buildEntries(List.of(
                Map.of("id", "1", "body", "a"),
                Map.of("id", "1", "body", "b")
        )));
    }
}

class SoPathsTest {
    @Test
    void encoding() {
        String[] p = SoPaths.soObjectPaths("acc", "docs", "folder/a file.txt");
        assertEquals("/acc/docs/objects/folder/a file.txt", p[0]);
        assertEquals("/acc/docs/objects/folder/a%20file.txt", p[1]);
    }

    @Test
    void parseUri() {
        String[] p = SoPaths.parseSoUri("so://photos/2024/");
        assertEquals("photos", p[0]);
        assertEquals("2024", p[1]);
    }
}
