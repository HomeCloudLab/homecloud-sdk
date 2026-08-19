package com.homecloudlab.sdk;

public record SyncOptions(boolean delete, boolean skip, int maxWorkers) {
    public static SyncOptions none() {
        return new SyncOptions(false, false, 0);
    }
}
