package com.homecloudlab.sdk;

public record EnableUrlOptions(boolean publicUrl, int rateLimitPerMinute) {
    public static EnableUrlOptions defaults() {
        return new EnableUrlOptions(false, 60);
    }
}
