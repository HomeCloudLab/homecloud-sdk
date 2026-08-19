package com.homecloudlab.sdk;

public record ReceiveOptions(int maxMessages, int waitSeconds, boolean delete) {
    public static ReceiveOptions defaults() {
        return new ReceiveOptions(1, 20, false);
    }
}
