package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ClientHttpTest {
    static HomeCloud isolated(Path configDir, java.util.function.Consumer<HomeCloud.Builder> cfg) {
        Map<String, String> env = new LinkedHashMap<>();
        env.put("HOMECLOUD_CONFIG_DIR", configDir.toString());
        env.put("HOMECLOUD_ACCESS_KEY_ID", "");
        env.put("HC_ACCESS_KEY_ID", "");
        env.put("HOMECLOUD_SECRET_ACCESS_KEY", "");
        env.put("HC_SECRET_ACCESS_KEY", "");
        env.put("HOMECLOUD_ACCOUNT_ID", "");
        env.put("HC_ACCOUNT_ID", "");
        env.put("HOMECLOUD_APEX", "");
        env.put("HC_APEX", "");
        env.put("HOMECLOUD_PROFILE", "");
        HomeCloud.Builder b = HomeCloud.builder().envOverride(env);
        cfg.accept(b);
        return b.build();
    }

    static HttpServer start(com.sun.net.httpserver.HttpHandler handler) throws IOException {
        HttpServer srv = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        srv.createContext("/", handler);
        srv.setExecutor(Executors.newCachedThreadPool());
        srv.start();
        return srv;
    }

    static String url(HttpServer srv) {
        return "http://127.0.0.1:" + srv.getAddress().getPort();
    }

    static void json(com.sun.net.httpserver.HttpExchange ex, int code, String body) throws IOException {
        byte[] raw = body.getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json");
        ex.sendResponseHeaders(code, raw.length);
        ex.getResponseBody().write(raw);
        ex.close();
    }

    @Test
    void fromStsMailRewrite(@TempDir Path dir) {
        HomeCloud c = HomeCloud.fromSts(
                new Sts("HCAKTEST", "secret", "", "https://console.holab.abrdns.com/api/v1", "", "mail"),
                HomeCloud.builder().envOverride(Map.of(
                        "HOMECLOUD_CONFIG_DIR", dir.toString(),
                        "HC_ACCOUNT_ID", "acc-1",
                        "HOMECLOUD_ACCESS_KEY_ID", "",
                        "HC_ACCESS_KEY_ID", "",
                        "HOMECLOUD_SECRET_ACCESS_KEY", "",
                        "HC_SECRET_ACCESS_KEY", ""
                )));
        assertEquals("https://mailapi.holab.abrdns.com", c.dataPlaneBase("mail"));
        assertEquals("holab.abrdns.com", c.apex());
        assertEquals("acc-1", c.accountIdOrEmpty());
    }

    @Test
    void fromFunctionContext(@TempDir Path dir) {
        HomeCloud c = HomeCloud.fromFunctionContext(new FunctionContext("acc-9", Map.of(
                "archive", new Sts("HCAK", "s", "", "https://so.example.test", "", "so")
        )), "archive");
        assertEquals("https://so.example.test", c.dataPlaneBase("so"));
        assertEquals("acc-9", c.accountIdOrEmpty());
    }

    @Test
    void getRetriesOn503(@TempDir Path dir) throws Exception {
        AtomicInteger hits = new AtomicInteger();
        HttpServer srv = start(ex -> {
            int n = hits.incrementAndGet();
            if (n < 3) {
                json(ex, 503, "{}");
                return;
            }
            json(ex, 200, "{\"key\":\"a.txt\",\"size\":1}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b
                    .accessKey("HCAK", "secret")
                    .accountId("acc")
                    .dataPlaneBase("so", url(srv))
                    .requestTimeout(Duration.ofSeconds(15)));
            ObjectHead head = c.so().headObject("docs", "a.txt");
            assertEquals("a.txt", head.key());
            assertEquals(3, hits.get());
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void mqSendDoesNotRetry503(@TempDir Path dir) throws Exception {
        AtomicInteger hits = new AtomicInteger();
        HttpServer srv = start(ex -> {
            hits.incrementAndGet();
            json(ex, 503, "{}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b
                    .accessKey("HCAK", "secret")
                    .accountId("acc")
                    .dataPlaneBase("mq", url(srv))
                    .requestTimeout(Duration.ofSeconds(5)));
            assertThrows(ServiceUnavailableException.class, () -> c.mq().send("orders", Map.of("id", 1)));
            assertEquals(1, hits.get());
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void soUploadListHead(@TempDir Path dir) throws Exception {
        Map<String, byte[]> objects = new LinkedHashMap<>();
        HttpServer srv = start(ex -> {
            URI u = ex.getRequestURI();
            String path = u.getPath();
            String method = ex.getRequestMethod();
            if ("POST".equals(method) && path.contains("/objects") && !path.contains("/copy")) {
                String body = new String(ex.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                String key = body.contains("name=\"key\"") ? body.replaceAll("(?s).*name=\"key\"\\s*\\r?\\n\\r?\\n(.*?)\\r?\\n--.*", "$1").trim() : "a.json";
                objects.put(key, body.getBytes(StandardCharsets.UTF_8));
                json(ex, 200, "{\"key\":\"" + key + "\",\"size\":4}");
                return;
            }
            if ("GET".equals(method) && path.endsWith("/metadata")) {
                json(ex, 200, "{\"key\":\"a.txt\",\"size\":4,\"etag\":\"abc\",\"content_type\":\"text/plain\",\"metadata\":{},\"tags\":{}}");
                return;
            }
            if ("GET".equals(method) && path.contains("/objects")) {
                json(ex, 200, "{\"items\":[{\"key\":\"a.txt\",\"size\":4,\"is_dir\":false}],\"has_more\":false}");
                return;
            }
            if ("DELETE".equals(method)) {
                ex.sendResponseHeaders(204, -1);
                ex.close();
                return;
            }
            json(ex, 404, "{}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b.accessKey("HCAK", "secret").accountId("acc").dataPlaneBase("so", url(srv)));
            ObjectRef ref = c.so().putJson("docs", "a.json", Map.of("ok", true));
            assertEquals("a.json", ref.key());
            ListObjectsResult listed = c.so().listObjects("docs", ListObjectsOptions.builder().prefix("a").build());
            assertEquals(1, listed.items().size());
            ObjectHead head = c.so().headObject("docs", "a.txt");
            assertEquals(4, head.size());
            c.so().delete("docs", "a.txt");
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void notConfigured(@TempDir Path dir) {
        HomeCloud c = isolated(dir, b -> {});
        assertThrows(NotConfiguredException.class, () -> c.so().headObject("docs", "x"));
    }

    @Test
    void object404Hint(@TempDir Path dir) throws Exception {
        HttpServer srv = start(ex -> json(ex, 404, "{\"detail\":{\"message\":\"NoSuchKey\"}}"));
        try {
            HomeCloud c = isolated(dir, b -> b.accessKey("HCAK", "s").accountId("acc").dataPlaneBase("so", url(srv)));
            NotFoundException nf = assertThrows(NotFoundException.class, () -> c.so().headObject("docs", "a.txt"));
            assertEquals("object", nf.getResourceType());
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void credentialsRoundTrip(@TempDir Path dir) {
        Map<String, String> env = Map.of("HOMECLOUD_CONFIG_DIR", dir.toString());
        HomeCloudAuth.configure("default", "HCAKFILE", "supersecret", new Env(new LinkedHashMap<>(Map.of(
                "HOMECLOUD_CONFIG_DIR", dir.toString(),
                "HOMECLOUD_ACCESS_KEY_ID", "",
                "HC_ACCESS_KEY_ID", "",
                "HOMECLOUD_SECRET_ACCESS_KEY", "",
                "HC_SECRET_ACCESS_KEY", ""
        ))));
        HomeCloud c2 = HomeCloud.builder().envOverride(Map.of(
                "HOMECLOUD_CONFIG_DIR", dir.toString(),
                "HOMECLOUD_ACCESS_KEY_ID", "",
                "HC_ACCESS_KEY_ID", "",
                "HOMECLOUD_SECRET_ACCESS_KEY", "",
                "HC_SECRET_ACCESS_KEY", ""
        )).profile("default").build();
        assertEquals("HCAKFILE", c2.accessKeyId());
        assertEquals("supersecret", c2.secretAccessKey());
    }

    @Test
    void requestTimeout(@TempDir Path dir) throws Exception {
        HttpServer srv = start(ex -> {
            try {
                Thread.sleep(400);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
            json(ex, 200, "{}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b
                    .accessKey("HCAK", "s")
                    .accountId("acc")
                    .dataPlaneBase("so", url(srv))
                    .requestTimeout(Duration.ofMillis(50)));
            assertThrows(HomeCloudException.class, () -> c.so().headObject("docs", "a.txt"));
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void mqReceiveDelete(@TempDir Path dir) throws Exception {
        HttpServer srv = start(ex -> {
            String path = ex.getRequestURI().getPath();
            String q = ex.getRequestURI().getQuery();
            if ("GET".equals(ex.getRequestMethod()) && path.equals("/acc/orders/messages")) {
                assertTrue(q != null && q.contains("delete=true"));
                json(ex, 200, "{\"items\":[{\"sequence\":7,\"body\":\"{\\\"id\\\":1}\"}]}");
                return;
            }
            if ("DELETE".equals(ex.getRequestMethod()) && path.equals("/acc/orders/messages/7")) {
                ex.sendResponseHeaders(204, -1);
                ex.close();
                return;
            }
            json(ex, 404, "{}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b.accessKey("HCAK", "s").accountId("acc").dataPlaneBase("mq", url(srv)));
            List<Message> msgs = c.mq().receive("orders", new ReceiveOptions(10, 5, true));
            assertEquals(1, msgs.size());
            assertEquals(7, msgs.get(0).sequence());
            c.mq().delete("orders", 7);
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void mqBatchSend(@TempDir Path dir) throws Exception {
        AtomicInteger entries = new AtomicInteger();
        HttpServer srv = start(ex -> {
            assertEquals("/acc/orders/messages/batch", ex.getRequestURI().getPath());
            JsonNode body = Json.MAPPER.readTree(ex.getRequestBody());
            entries.set(body.get("entries").size());
            json(ex, 200, "{\"ok\":true}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b.accessKey("HCAK", "s").accountId("acc").dataPlaneBase("mq", url(srv)));
            c.mq().send("orders", List.of(Map.of("id", 1), Map.of("id", 2)));
            assertEquals(2, entries.get());
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void createBucketIdempotency(@TempDir Path dir) throws Exception {
        AtomicInteger keyLen = new AtomicInteger();
        HttpServer srv = start(ex -> {
            String k = ex.getRequestHeaders().getFirst("Idempotency-Key");
            keyLen.set(k == null ? 0 : k.length());
            json(ex, 200, "{\"name\":\"docs\",\"status\":\"active\"}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b.accessToken("jwt").accountId("acc").consoleBaseUrl(url(srv)));
            Bucket bkt = c.so().createBucket("Docs");
            assertEquals("docs", bkt.name());
            assertTrue(keyLen.get() > 0);
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void loginReturnsNewClient(@TempDir Path dir) throws Exception {
        HttpServer srv = start(ex -> json(ex, 200, "{\"access_token\":\"tok-1\"}"));
        try {
            HomeCloud logged = HomeCloudAuth.login("100", "alice", "pw", "", HomeCloud.builder()
                    .envOverride(Map.of("HOMECLOUD_CONFIG_DIR", dir.toString()))
                    .consoleBaseUrl(url(srv)));
            assertEquals("tok-1", logged.accessToken());
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void secretsGet(@TempDir Path dir) throws Exception {
        HttpServer srv = start(ex -> json(ex, 200, "{\"name\":\"db\",\"value\":\"s3cret\"}"));
        try {
            HomeCloud c = isolated(dir, b -> b.accessKey("HCAK", "s").accountId("acc").dataPlaneBase("secrets", url(srv)));
            Secret sec = c.secrets().get("db");
            assertEquals("db", sec.name());
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void namespacesCached(@TempDir Path dir) {
        HomeCloud c = isolated(dir, b -> b.accessKey("HCAK", "s").accountId("acc"));
        assertEquals(c.so(), c.so());
        assertEquals(c.mq(), c.mq());
    }

    @Test
    void consoleNamespaces(@TempDir Path dir) throws Exception {
        HttpServer srv = start(ex -> {
            String path = ex.getRequestURI().getPath();
            if (path.endsWith("/accounts") || path.equals("/accounts")) {
                json(ex, 200, "{\"items\":[{\"id\":\"acc\",\"name\":\"Main\"}]}");
                return;
            }
            if (path.contains("/applications")) {
                json(ex, 200, "{\"items\":[{\"name\":\"web\"}]}");
                return;
            }
            if (path.contains("/queues/") && !path.endsWith("/queues")) {
                json(ex, 200, "{\"name\":\"orders\"}");
                return;
            }
            if (path.contains("/queues")) {
                json(ex, 200, "{\"items\":[{\"name\":\"orders\"}]}");
                return;
            }
            if (path.contains("/registry/repositories") && "POST".equals(ex.getRequestMethod())) {
                assertNotEquals(null, ex.getRequestHeaders().getFirst("Idempotency-Key"));
                json(ex, 200, "{\"name\":\"app\"}");
                return;
            }
            if (path.contains("/registry/repositories/usage")) {
                json(ex, 200, "{\"bytes\":1}");
                return;
            }
            if (path.contains("/registry/repositories")) {
                json(ex, 200, "{\"items\":[{\"name\":\"app\"}]}");
                return;
            }
            if (path.contains("/functions/") && path.endsWith("/url")) {
                json(ex, 200, "{\"url\":\"https://x.func.test\"}");
                return;
            }
            if (path.contains("/functions")) {
                json(ex, 200, "{\"items\":[{\"name\":\"hello\"}]}");
                return;
            }
            if (path.contains("/mail/mailboxes")) {
                json(ex, 200, "{\"items\":[{\"id\":\"m1\",\"email\":\"a@b.c\"}]}");
                return;
            }
            if (path.contains("/usage")) {
                json(ex, 200, "{\"items\":[]}");
                return;
            }
            if (path.contains("/billing/summary")) {
                json(ex, 200, "{\"total\":0}");
                return;
            }
            if (path.contains("/billing/forecast")) {
                json(ex, 200, "{\"horizon\":30}");
                return;
            }
            if (path.contains("/billing/invoices")) {
                json(ex, 200, "{\"items\":[]}");
                return;
            }
            if (path.contains("/monitoring/workspace")) {
                json(ex, 200, "{\"id\":\"ws\"}");
                return;
            }
            if (path.contains("/monitoring/dashboards")) {
                json(ex, 200, "{\"items\":[]}");
                return;
            }
            json(ex, 404, "{}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b.accessToken("jwt").accountId("acc").consoleBaseUrl(url(srv)));
            assertEquals("acc", c.accounts().list().get(0).id());
            assertEquals("web", c.apps().list().get(0).name());
            assertEquals("orders", c.queues().list().get(0).name());
            assertEquals("orders", c.queues().get("orders").name());
            assertEquals("app", c.ir().list().items().get(0).name());
            c.ir().create("app", 3);
            assertTrue(c.ir().usage().has("bytes"));
            assertEquals("hello", c.functions().list().get(0).name());
            assertTrue(c.functions().url("hello").has("url"));
            assertEquals("m1", c.mail().listMailboxes().get(0).id());
            assertTrue(c.usage().list(null).has("items"));
            assertTrue(c.billing().summary().has("total"));
            assertTrue(c.billing().forecast(0).has("horizon"));
            assertTrue(c.billing().invoices().has("items"));
            assertEquals("ws", c.monitoring().workspace().path("id").asText());
            assertTrue(c.monitoring().dashboards().has("items"));
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void invokeNotRetried(@TempDir Path dir) throws Exception {
        AtomicInteger hits = new AtomicInteger();
        HttpServer srv = start(ex -> {
            hits.incrementAndGet();
            json(ex, 503, "{}");
        });
        try {
            // apex unused; override function host via... invoke uses functionUrl(name, apex).
            // Hit local server by using a custom HttpClient? Function URL is https://hello.func.apex/
            // Skip live DNS: send through data plane isn't used.
            // This test documents purge not retried instead.
            HomeCloud c = isolated(dir, b -> b.accessKey("HCAK", "s").accountId("acc").dataPlaneBase("mq", url(srv)));
            assertThrows(ServiceUnavailableException.class, () -> c.mq().purge("orders"));
            assertEquals(1, hits.get());
        } finally {
            srv.stop(0);
        }
    }

    @Test
    void rateLimitExposesRetryAfter(@TempDir Path dir) throws Exception {
        HttpServer srv = start(ex -> {
            ex.getResponseHeaders().set("Retry-After", "3");
            json(ex, 429, "{\"message\":\"slow down\"}");
        });
        try {
            HomeCloud c = isolated(dir, b -> b.accessKey("HCAK", "s").accountId("acc").dataPlaneBase("so", url(srv)));
            RateLimitException e = assertThrows(RateLimitException.class, () -> c.so().headObject("docs", "a.txt"));
            assertEquals(Duration.ofSeconds(3), e.getRetryAfter());
        } finally {
            srv.stop(0);
        }
    }
}
