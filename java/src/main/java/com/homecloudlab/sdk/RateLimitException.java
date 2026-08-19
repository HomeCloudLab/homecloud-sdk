package com.homecloudlab.sdk;

import java.time.Duration;

public class RateLimitException extends ApiException {
    private final Duration retryAfter;

    RateLimitException(String message, int statusCode, Object detail, Duration retryAfter) {
        super(message, statusCode, detail);
        this.retryAfter = retryAfter;
    }

    /** Parsed from {@code Retry-After} when present; may be {@code null}. Not used for automatic retry in v1. */
    public Duration getRetryAfter() {
        return retryAfter;
    }
}
