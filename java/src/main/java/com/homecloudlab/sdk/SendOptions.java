package com.homecloudlab.sdk;

import java.util.Map;

public record SendOptions(Map<String, String> headers) {
    public static SendOptions none() {
        return new SendOptions(null);
    }
}
