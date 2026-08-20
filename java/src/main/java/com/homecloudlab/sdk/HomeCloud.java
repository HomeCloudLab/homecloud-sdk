package com.homecloudlab.sdk;

import com.fasterxml.jackson.databind.JsonNode;

import java.net.URI;
import java.net.http.HttpClient;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;

/**
 * HomeCloud SDK client. Thread-safe after {@link #builder()}{@code .build()} / factories.
 * Reuse as a singleton (for example a Spring {@code @Bean}). One shared {@link HttpClient} per instance.
 */
public final class HomeCloud implements AutoCloseable {
    private final String accessKeyId;
    private final String secretAccessKey;
    private final AtomicReference<String> accountId;
    private final String apex;
    private final String profileName;
    private final String sessionToken;
    private final String accessToken;
    private final String consoleBaseUrl;
    private final Map<String, String> dataPlaneBases;
    private final Duration requestTimeout;
    private final Duration connectTimeout;
    private final HttpClient httpClient;
    private final Env env;
    private final boolean closeHttpClient;

    private final So so;
    private final Mq mq;
    private final Secrets secrets;
    private final Mail mail;
    private final Functions functions;
    private final Accounts accounts;
    private final Apps apps;
    private final Queues queues;
    private final Ir ir;
    private final Usage usage;
    private final Billing billing;
    private final Monitoring monitoring;

    HomeCloud(Builder b) {
        this.env = b.env == null ? new Env(null) : b.env;
        String apex = Env.trimSlash(b.apex);
        String profileName = b.profileName;
        String accountId = b.accountId;
        String accessKeyId = b.accessKeyId;
        String secretAccessKey = b.secretAccessKey;
        String sessionToken = b.sessionToken == null ? "" : b.sessionToken;
        String accessToken = b.accessToken == null ? "" : b.accessToken;
        String consoleBaseUrl = Env.trimSlash(b.consoleBaseUrl);
        Map<String, String> dataPlaneBases = new LinkedHashMap<>();
        if (b.dataPlaneBases != null) {
            b.dataPlaneBases.forEach((k, v) -> dataPlaneBases.put(k, Env.trimSlash(v)));
        }

        if (!b.skipFileAndEnv) {
            Loaded loaded = loadFileAndEnv(this.env, profileName);
            if (isBlank(apex)) {
                apex = loaded.apex;
            }
            if (isBlank(profileName)) {
                profileName = loaded.profileName;
            }
            if (isBlank(accountId)) {
                accountId = loaded.accountId;
            }
            if (isBlank(accessKeyId)) {
                accessKeyId = loaded.accessKeyId;
                secretAccessKey = loaded.secretAccessKey;
            }
            if (isBlank(accessToken)) {
                accessToken = loaded.accessToken;
            }
            if (isBlank(accountId)) {
                accountId = loaded.accountId;
            }
        }

        // Explicit builder fields already applied above except we must re-apply
        // constructor-wins: Builder values that were set override file/env.
        if (!isBlank(b.apex)) {
            apex = Env.trimSlash(b.apex);
        }
        if (!isBlank(b.profileName)) {
            profileName = b.profileName;
        }
        if (!isBlank(b.accountId)) {
            accountId = b.accountId;
        }
        if (!isBlank(b.accessKeyId)) {
            accessKeyId = b.accessKeyId;
            secretAccessKey = b.secretAccessKey;
        }
        if (b.sessionToken != null) {
            sessionToken = b.sessionToken;
        }
        if (b.accessToken != null) {
            accessToken = b.accessToken;
        }
        if (!isBlank(b.consoleBaseUrl)) {
            consoleBaseUrl = Env.trimSlash(b.consoleBaseUrl);
        }
        if (b.dataPlaneBases != null) {
            b.dataPlaneBases.forEach((k, v) -> dataPlaneBases.put(k, Env.trimSlash(v)));
        }

        if (isBlank(apex)) {
            apex = Env.DEFAULT_APEX;
        }
        if (isBlank(profileName)) {
            profileName = Env.DEFAULT_PROFILE;
        }

        this.accessKeyId = accessKeyId == null ? "" : accessKeyId;
        this.secretAccessKey = secretAccessKey == null ? "" : secretAccessKey;
        this.accountId = new AtomicReference<>(accountId == null ? "" : accountId);
        this.apex = apex;
        this.profileName = profileName;
        this.sessionToken = sessionToken;
        this.accessToken = accessToken;
        this.consoleBaseUrl = consoleBaseUrl;
        this.dataPlaneBases = Map.copyOf(dataPlaneBases);
        this.requestTimeout = b.requestTimeout == null ? Env.DEFAULT_REQUEST_TIMEOUT : b.requestTimeout;
        this.connectTimeout = b.connectTimeout == null ? Env.DEFAULT_CONNECT_TIMEOUT : b.connectTimeout;
        if (b.httpClient != null) {
            this.httpClient = b.httpClient;
            this.closeHttpClient = false;
        } else {
            this.httpClient = HttpClient.newBuilder()
                    .connectTimeout(this.connectTimeout)
                    .followRedirects(HttpClient.Redirect.NORMAL)
                    .build();
            this.closeHttpClient = true;
        }

        this.so = new So(this);
        this.mq = new Mq(this);
        this.secrets = new Secrets(this);
        this.mail = new Mail(this);
        this.functions = new Functions(this);
        this.accounts = new Accounts(this);
        this.apps = new Apps(this);
        this.queues = new Queues(this);
        this.ir = new Ir(this);
        this.usage = new Usage(this);
        this.billing = new Billing(this);
        this.monitoring = new Monitoring(this);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static HomeCloud fromEnv() {
        return builder().build();
    }

    public static HomeCloud fromCredentials(String accessKeyId, String secretAccessKey) {
        return builder().accessKey(accessKeyId, secretAccessKey).build();
    }

    public static HomeCloud fromProfile(String profile) {
        return builder().profile(profile).build();
    }

    public static HomeCloud fromSts(Sts sts) {
        return fromSts(sts, builder());
    }

    static HomeCloud fromSts(Sts sts, Builder extra) {
        Objects.requireNonNull(sts, "sts");
        Env env = extra.env == null ? new Env(null) : extra.env;
        String aid = env.accountId();
        String base = Env.trimSlash(first(sts.baseUrl(), sts.mailBaseUrl()));
        String resourceType = sts.resourceType() == null ? "" : sts.resourceType().trim().toLowerCase();
        String resolvedApex = env.apex();
        Map<String, String> dataPlane = new LinkedHashMap<>();

        if (!base.isEmpty()) {
            URI u = URI.create(base.contains("://") ? base : "https://" + base);
            String host = u.getHost() == null ? "" : u.getHost();
            if ("mail".equals(resourceType)) {
                if (host.startsWith("console.") || base.contains("/api/v1")) {
                    if (host.startsWith("console.")) {
                        resolvedApex = Env.firstNonEmpty(resolvedApex, host.substring("console.".length()));
                    }
                    if (resolvedApex.isEmpty()) {
                        resolvedApex = Env.DEFAULT_APEX;
                    }
                    dataPlane.put("mail", Env.trimSlash(Env.mailApiUrl(resolvedApex)));
                } else {
                    dataPlane.put("mail", base);
                    if (host.startsWith("mailapi.")) {
                        resolvedApex = Env.firstNonEmpty(resolvedApex, host.substring("mailapi.".length()));
                    }
                }
            } else if ("so".equals(resourceType) || "mq".equals(resourceType) || "secrets".equals(resourceType)) {
                dataPlane.put(resourceType, base);
                String prefix = resourceType + ".";
                if (host.startsWith(prefix)) {
                    resolvedApex = Env.firstNonEmpty(resolvedApex, host.substring(prefix.length()));
                }
            }
        } else if ("mail".equals(resourceType)) {
            resolvedApex = Env.firstNonEmpty(resolvedApex, Env.DEFAULT_APEX);
            dataPlane.put("mail", Env.trimSlash(Env.mailApiUrl(resolvedApex)));
        }
        if (resolvedApex.isEmpty()) {
            resolvedApex = Env.DEFAULT_APEX;
        }

        Builder b = extra.copy()
                .accessKey(sts.accessKeyId(), sts.secretAccessKey())
                .apex(resolvedApex)
                .dataPlaneBases(dataPlane);
        if (sts.sessionToken() != null && !sts.sessionToken().isBlank()) {
            b.sessionToken(sts.sessionToken());
        }
        if (!aid.isEmpty()) {
            b.accountId(aid);
        }
        return b.build();
    }

    public static HomeCloud fromFunctionContext(FunctionContext ctx, String binding) {
        Map<String, Sts> stsMap = ctx == null || ctx.sts() == null ? Map.of() : ctx.sts();
        if (stsMap.isEmpty()) {
            String raw = System.getenv("HC_STS_JSON");
            if (raw != null && !raw.isBlank()) {
                try {
                    stsMap = Json.MAPPER.readValue(raw, Json.MAPPER.getTypeFactory()
                            .constructMapType(LinkedHashMap.class, String.class, Sts.class));
                } catch (Exception ignored) {
                    stsMap = Map.of();
                }
            }
        }
        Sts entry = stsMap.get(binding);
        if (entry == null || entry.accessKeyId() == null || entry.accessKeyId().isBlank()) {
            throw new HomeCloudException("Missing STS for binding '" + binding
                    + "'. Set Bindings + execution_role on the function (no manual Access Key ENV needed).");
        }
        String accountId = ctx == null ? "" : nullToEmpty(ctx.accountId());
        if (accountId.isEmpty()) {
            accountId = nullToEmpty(System.getenv("HC_ACCOUNT_ID"));
        }
        Builder b = builder();
        if (!accountId.isEmpty()) {
            b.accountId(accountId);
        }
        return fromSts(entry, b);
    }

    public So so() { return so; }
    public Mq mq() { return mq; }
    public Secrets secrets() { return secrets; }
    public Mail mail() { return mail; }
    public Functions functions() { return functions; }
    public Accounts accounts() { return accounts; }
    public Apps apps() { return apps; }
    public Queues queues() { return queues; }
    public Ir ir() { return ir; }
    public Usage usage() { return usage; }
    public Billing billing() { return billing; }
    public Monitoring monitoring() { return monitoring; }

    public String accountId() {
        ensureAccountId();
        return accountId.get();
    }

    /**
     * Best-effort close. Java 17 {@link HttpClient} is not closeable; idle keep-alive connections expire on their own.
     * A custom client passed to {@link Builder#httpClient(HttpClient)} is not closed.
     */
    @Override
    public void close() {
        // Java 17 HttpClient has no shutdown API.
    }

    Builder toBuilder() {
        Builder b = new Builder();
        b.env = env;
        b.skipFileAndEnv = true;
        b.accessKeyId = accessKeyId;
        b.secretAccessKey = secretAccessKey;
        b.accountId = accountId.get();
        b.apex = apex;
        b.profileName = profileName;
        b.sessionToken = sessionToken;
        b.accessToken = accessToken;
        b.consoleBaseUrl = consoleBaseUrl;
        b.dataPlaneBases = new LinkedHashMap<>(dataPlaneBases);
        b.requestTimeout = requestTimeout;
        b.connectTimeout = connectTimeout;
        b.httpClient = httpClient;
        return b;
    }

    String accessKeyId() { return accessKeyId; }
    String secretAccessKey() { return secretAccessKey; }
    String sessionToken() { return sessionToken; }
    String accessToken() { return accessToken; }
    String apex() { return apex; }
    String profileName() { return profileName; }
    Duration requestTimeout() { return requestTimeout == null ? Duration.ZERO : requestTimeout; }
    HttpClient httpClient() { return httpClient; }
    String accountIdOrEmpty() { return nullToEmpty(accountId.get()); }
    Env env() { return env; }

    boolean hasAccessKey() {
        return !accessKeyId.isEmpty() && !secretAccessKey.isEmpty();
    }

    void requireAccessKey() {
        if (!hasAccessKey()) {
            throw new NotConfiguredException();
        }
    }

    void requireConsole() {
        if (accessToken.isEmpty()) {
            throw new NotLoggedInException();
        }
    }

    void ensureAccountId() {
        if (!accountIdOrEmpty().isEmpty()) {
            return;
        }
        requireAccessKey();
        Transport.Spec spec = new Transport.Spec();
        spec.method = "GET";
        spec.url = trimSlash(dataPlaneBase("so")) + Env.WHOAMI_PATH;
        spec.signPath = Env.WHOAMI_PATH;
        spec.accountId = Env.WHOAMI_ACCOUNT_SENTINEL;
        spec.signed = true;
        spec.retry = Transport.RetryMode.IDEMPOTENT;
        byte[] raw = Transport.doRequest(this, spec);
        JsonNode node = Json.parse(raw);
        String id = node.path("account_id").asText("");
        if (id.isEmpty()) {
            throw new HomeCloudException("whoami did not return account_id");
        }
        accountId.set(id);
        rememberAccount(id);
    }

    void setAccountId(String id) {
        accountId.set(id);
        rememberAccount(id);
    }

    synchronized void rememberAccount(String id) {
        var sessions = CredentialsStore.loadSessionFile(CredentialsStore.sessionPath(env));
        var current = sessions.getOrDefault(profileName, new CredentialsStore.ProfileSession());
        sessions.put(profileName, new CredentialsStore.ProfileSession(current.accessToken(), id, id));
        try {
            CredentialsStore.saveSessionFile(CredentialsStore.sessionPath(env), sessions);
        } catch (HomeCloudException ignored) {
            // best-effort
        }
    }

    synchronized void persistAccessToken(String token) {
        var sessions = CredentialsStore.loadSessionFile(CredentialsStore.sessionPath(env));
        var current = sessions.getOrDefault(profileName, new CredentialsStore.ProfileSession());
        sessions.put(profileName, new CredentialsStore.ProfileSession(token, current.activeAccountId(), current.lastUsedAccountId()));
        CredentialsStore.saveSessionFile(CredentialsStore.sessionPath(env), sessions);
    }

    boolean hasMailDataPlaneOverride() {
        String u = dataPlaneBases.get("mail");
        return u != null && !u.isEmpty();
    }

    String dataPlaneBase(String service) {
        String u = dataPlaneBases.get(service);
        if (u != null && !u.isEmpty()) {
            return trimSlash(u);
        }
        return switch (service) {
            case "mq" -> Env.mqUrl(apex);
            case "secrets" -> Env.secretsUrl(apex);
            case "mail" -> Env.mailApiUrl(apex);
            default -> Env.soUrl(apex);
        };
    }

    String consoleBase() {
        if (!isBlank(consoleBaseUrl)) {
            return trimSlash(consoleBaseUrl);
        }
        return trimSlash(Env.consoleUrl(apex));
    }

    byte[] dataPlane(String service, String method, String signPath, String urlPath, Transport.Spec extra) {
        requireAccessKey();
        ensureAccountId();
        Transport.Spec spec = extra == null ? new Transport.Spec() : extra;
        spec.method = method;
        spec.signPath = signPath;
        spec.accountId = accountIdOrEmpty();
        spec.signed = true;
        if (extra == null) {
            spec.retry = Transport.retryFromMethod(method);
        }
        if (isBlank(spec.url)) {
            spec.url = dataPlaneBase(service) + (isBlank(urlPath) ? signPath : urlPath);
        }
        return Transport.doRequest(this, spec);
    }

    byte[] dataPlaneJson(
            String service,
            String method,
            String signPath,
            String urlPath,
            Map<String, String> query,
            Object jsonBody,
            Transport.RetryMode retry) {
        Transport.Spec spec = new Transport.Spec();
        spec.retry = retry == null ? Transport.retryFromMethod(method) : retry;
        spec.query = query;
        spec.jsonBody = jsonBody;
        return dataPlane(service, method, signPath, urlPath, spec);
    }

    byte[] consoleJson(String method, String pathSeg, boolean requireAuth, Object jsonBody, Map<String, String> query, String idempotency, Transport.RetryMode retry) {
        if (requireAuth) {
            requireConsole();
        }
        String rel = pathSeg.startsWith("/") ? pathSeg.substring(1) : pathSeg;
        Transport.Spec spec = new Transport.Spec();
        spec.method = method;
        spec.url = consoleBase() + "/" + rel;
        spec.bearer = requireAuth;
        spec.jsonBody = jsonBody;
        spec.query = query;
        spec.retry = retry == null ? Transport.retryFromMethod(method) : retry;
        if (idempotency != null && !idempotency.isEmpty()) {
            spec.idempotencyKey = idempotency;
            spec.retry = Transport.RetryMode.IF_IDEMPOTENCY;
        }
        return Transport.doRequest(this, spec);
    }

    byte[] consoleSignedJson(String method, String pathSeg, String account, Map<String, String> query) {
        return consoleSignedJson(method, pathSeg, account, null, query, null);
    }

    byte[] consoleSignedJson(
            String method,
            String pathSeg,
            String account,
            Object jsonBody,
            Map<String, String> query,
            String idempotency) {
        requireAccessKey();
        String rel = pathSeg.startsWith("/") ? pathSeg.substring(1) : pathSeg;
        Transport.Spec spec = new Transport.Spec();
        spec.method = method;
        spec.url = consoleBase() + "/" + rel;
        spec.signPath = "/api/v1/" + rel;
        spec.accountId = account;
        spec.signed = true;
        spec.jsonBody = jsonBody;
        spec.query = query;
        spec.retry = Transport.retryFromMethod(method);
        if (idempotency != null && !idempotency.isEmpty()) {
            spec.idempotencyKey = idempotency;
            spec.retry = Transport.RetryMode.IF_IDEMPOTENCY;
        }
        return Transport.doRequest(this, spec);
    }

    private static Loaded loadFileAndEnv(Env env, String explicitProfile) {
        String profile = explicitProfile;
        if (isBlank(profile)) {
            profile = env.profile();
        }
        String apex = env.platformApex();
        String accountId = "";
        String accessKeyId = "";
        String secret = "";
        String accessToken = "";

        var cf = CredentialsStore.loadCredentialsFile(CredentialsStore.credentialsPath(env), env.platformApex());
        if (cf != null) {
            String name = profile;
            if (isBlank(name)) {
                name = cf.defaultProfile();
            }
            if (isBlank(name)) {
                name = Env.DEFAULT_PROFILE;
            }
            profile = name;
            var p = cf.profiles().get(name);
            if (p != null) {
                if (!isBlank(p.apex())) {
                    apex = p.apex();
                }
                accountId = p.defaultAccountId();
                accessKeyId = p.accessKeyId();
                secret = p.secretAccessKey();
            }
        } else if (isBlank(profile)) {
            profile = Env.DEFAULT_PROFILE;
        }

        var sessions = CredentialsStore.loadSessionFile(CredentialsStore.sessionPath(env));
        var s = sessions.get(profile);
        if (s != null) {
            accessToken = s.accessToken();
            if (!isBlank(s.activeAccountId())) {
                accountId = s.activeAccountId();
            } else if (isBlank(accountId)) {
                accountId = s.lastUsedAccountId();
            }
        }

        if (!env.apex().isEmpty()) {
            apex = env.apex();
        }
        if (!env.accountId().isEmpty()) {
            accountId = env.accountId();
        }
        if (!env.accessKeyId().isEmpty()) {
            accessKeyId = env.accessKeyId();
        }
        if (!env.secretAccessKey().isEmpty()) {
            secret = env.secretAccessKey();
        }
        if (!env.profile().isEmpty()) {
            profile = env.profile();
        }
        return new Loaded(apex, profile, accountId, accessKeyId, secret, accessToken);
    }

    private record Loaded(String apex, String profileName, String accountId, String accessKeyId, String secretAccessKey, String accessToken) {}

    private static boolean isBlank(String s) {
        return s == null || s.isBlank();
    }

    private static String nullToEmpty(String s) {
        return s == null ? "" : s;
    }

    private static String first(String a, String b) {
        return isBlank(a) ? nullToEmpty(b) : a;
    }

    private static String trimSlash(String s) {
        return Env.trimSlash(s);
    }

    public static final class Builder {
        private Env env;
        boolean skipFileAndEnv;
        String accessKeyId = "";
        String secretAccessKey = "";
        String accountId = "";
        String apex = "";
        String profileName = "";
        String sessionToken;
        String accessToken;
        String consoleBaseUrl = "";
        Map<String, String> dataPlaneBases;
        Duration requestTimeout;
        Duration connectTimeout;
        HttpClient httpClient;

        public Builder accessKey(String id, String secret) {
            this.accessKeyId = id;
            this.secretAccessKey = secret;
            return this;
        }

        public Builder accountId(String accountId) {
            this.accountId = accountId;
            return this;
        }

        public Builder apex(String apex) {
            this.apex = apex;
            return this;
        }

        public Builder profile(String profile) {
            this.profileName = profile;
            return this;
        }

        public Builder sessionToken(String sessionToken) {
            this.sessionToken = sessionToken;
            return this;
        }

        public Builder accessToken(String accessToken) {
            this.accessToken = accessToken;
            return this;
        }

        public Builder consoleBaseUrl(String url) {
            this.consoleBaseUrl = url;
            return this;
        }

        public Builder dataPlaneBase(String service, String baseUrl) {
            if (this.dataPlaneBases == null) {
                this.dataPlaneBases = new LinkedHashMap<>();
            }
            this.dataPlaneBases.put(service, baseUrl);
            return this;
        }

        public Builder dataPlaneBases(Map<String, String> bases) {
            this.dataPlaneBases = new LinkedHashMap<>(bases);
            return this;
        }

        public Builder requestTimeout(Duration timeout) {
            this.requestTimeout = timeout;
            return this;
        }

        public Builder connectTimeout(Duration timeout) {
            this.connectTimeout = timeout;
            return this;
        }

        public Builder httpClient(HttpClient httpClient) {
            this.httpClient = httpClient;
            return this;
        }

        Builder envOverride(Map<String, String> override) {
            this.env = new Env(override);
            return this;
        }

        Builder skipFileAndEnv(boolean skip) {
            this.skipFileAndEnv = skip;
            return this;
        }

        Builder copy() {
            Builder n = new Builder();
            n.env = env;
            n.skipFileAndEnv = skipFileAndEnv;
            n.accessKeyId = accessKeyId;
            n.secretAccessKey = secretAccessKey;
            n.accountId = accountId;
            n.apex = apex;
            n.profileName = profileName;
            n.sessionToken = sessionToken;
            n.accessToken = accessToken;
            n.consoleBaseUrl = consoleBaseUrl;
            n.dataPlaneBases = dataPlaneBases == null ? null : new LinkedHashMap<>(dataPlaneBases);
            n.requestTimeout = requestTimeout;
            n.connectTimeout = connectTimeout;
            n.httpClient = httpClient;
            return n;
        }

        public HomeCloud build() {
            return new HomeCloud(this);
        }
    }
}
