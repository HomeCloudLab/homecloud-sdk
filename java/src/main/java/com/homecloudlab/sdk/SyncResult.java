package com.homecloudlab.sdk;

public record SyncResult(int uploaded, int downloaded, int copied, int skipped, int deleted) {
    static SyncResult empty() {
        return new SyncResult(0, 0, 0, 0, 0);
    }
}
