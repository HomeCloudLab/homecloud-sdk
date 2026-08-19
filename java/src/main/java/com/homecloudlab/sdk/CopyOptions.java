package com.homecloudlab.sdk;

public record CopyOptions(String sourceBucket) {
    public static CopyOptions none() {
        return new CopyOptions("");
    }
}
