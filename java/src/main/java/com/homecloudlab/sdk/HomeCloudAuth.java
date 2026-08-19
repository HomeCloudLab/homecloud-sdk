package com.homecloudlab.sdk;

import java.awt.Desktop;
import java.net.URI;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Interactive / file auth helpers. Returns a <strong>new</strong> {@link HomeCloud}; never mutates an existing client.
 */
public final class HomeCloudAuth {
    private HomeCloudAuth() {}

    public static HomeCloud login(String account, String username, String password) {
        return login(account, username, password, null, HomeCloud.builder());
    }

    public static HomeCloud login(String account, String username, String password, String mfaCode) {
        return login(account, username, password, mfaCode, HomeCloud.builder());
    }

    static HomeCloud login(String account, String username, String password, String mfaCode, HomeCloud.Builder builder) {
        HomeCloud bootstrap = builder.build();
        Map<String, String> body = new LinkedHashMap<>();
        body.put("account", account);
        body.put("username", username);
        body.put("password", password);
        if (mfaCode != null && !mfaCode.isBlank()) {
            body.put("mfa_code", mfaCode);
        }
        byte[] raw = bootstrap.consoleJson("POST", "auth/login", false, body, null, null, Transport.RetryMode.NEVER);
        String token = Json.parse(raw).path("access_token").asText("");
        if (token.isEmpty()) {
            throw new HomeCloudException("Login failed");
        }
        bootstrap.persistAccessToken(token);
        return bootstrap.toBuilder().accessToken(token).build();
    }

    public static HomeCloud loginBrowser() {
        return loginBrowser(LoginBrowserOptions.defaults(), HomeCloud.builder());
    }

    public static HomeCloud loginBrowser(LoginBrowserOptions opts) {
        return loginBrowser(opts, HomeCloud.builder());
    }

    static HomeCloud loginBrowser(LoginBrowserOptions opts, HomeCloud.Builder builder) {
        if (opts == null) {
            opts = LoginBrowserOptions.defaults();
        }
        HomeCloud bootstrap = builder.build();
        Object startBody = null;
        if (opts.mfaToken() != null && !opts.mfaToken().isBlank()) {
            startBody = Map.of("mfa_token", opts.mfaToken());
        }
        byte[] raw = bootstrap.consoleJson("POST", "auth/cli/session", false, startBody, null, null, Transport.RetryMode.NEVER);
        var start = Json.parse(raw);
        String sessionId = start.path("session_id").asText("");
        String uri = start.path("verification_uri").asText("");
        if (sessionId.isEmpty() || uri.isEmpty()) {
            throw new HomeCloudException("Failed to start browser login session");
        }
        if (opts.openBrowser()) {
            openBrowser(uri);
        }
        if (opts.onWaiting() != null) {
            opts.onWaiting().accept(uri);
        }
        Duration interval = Duration.ofSeconds(start.path("interval").asInt(2));
        if (interval.compareTo(Duration.ofSeconds(1)) < 0) {
            interval = Duration.ofSeconds(2);
        }
        if (opts.pollEvery() != null && !opts.pollEvery().isZero() && !opts.pollEvery().isNegative()) {
            interval = opts.pollEvery();
        }
        int expiresIn = start.path("expires_in").asInt(0);
        Duration expires = expiresIn <= 0 ? Duration.ofMinutes(10) : Duration.ofSeconds(expiresIn);
        Instant deadline = Instant.now().plus(expires);
        while (Instant.now().isBefore(deadline)) {
            if (Thread.currentThread().isInterrupted()) {
                throw new HomeCloudException("Request cancelled");
            }
            byte[] poll = bootstrap.consoleJson("GET", "auth/cli/session/" + sessionId, false, null, null, null, Transport.RetryMode.NEVER);
            var status = Json.parse(poll);
            switch (status.path("status").asText("")) {
                case "complete" -> {
                    String token = status.path("access_token").asText("");
                    if (token.isEmpty()) {
                        throw new HomeCloudException("Browser login completed without access token");
                    }
                    bootstrap.persistAccessToken(token);
                    return bootstrap.toBuilder().accessToken(token).build();
                }
                case "expired" -> throw new HomeCloudException("Browser login session expired");
                default -> {
                    try {
                        Thread.sleep(interval.toMillis());
                    } catch (InterruptedException e) {
                        Thread.currentThread().interrupt();
                        throw new HomeCloudException("Request cancelled", e);
                    }
                }
            }
        }
        throw new HomeCloudException("Browser login timed out");
    }

    /** Writes Access Keys into {@code ~/.homecloud/credentials} for the default profile. */
    public static void configure(String accessKeyId, String secretAccessKey) {
        configure(Env.DEFAULT_PROFILE, accessKeyId, secretAccessKey, HomeCloud.builder().build().env());
    }

    static void configure(String profile, String accessKeyId, String secretAccessKey, Env env) {
        var path = CredentialsStore.credentialsPath(env);
        var cf = CredentialsStore.loadCredentialsFile(path, env.platformApex());
        Map<String, CredentialsStore.ProfileConfig> profiles = new LinkedHashMap<>();
        String defaultProfile = profile;
        int version = 2;
        if (cf != null) {
            profiles.putAll(cf.profiles());
            defaultProfile = profile;
            version = cf.version();
        }
        profiles.put(profile, new CredentialsStore.ProfileConfig(profile, "", "", accessKeyId, secretAccessKey));
        CredentialsStore.saveCredentialsFile(new CredentialsStore.CredentialsFile(version, defaultProfile, profiles), path);
    }

    private static void openBrowser(String uri) {
        try {
            if (Desktop.isDesktopSupported() && Desktop.getDesktop().isSupported(Desktop.Action.BROWSE)) {
                Desktop.getDesktop().browse(URI.create(uri));
            }
        } catch (Exception ignored) {
            // best-effort
        }
    }
}
