package com.homecloudlab.sdk;

import java.util.Map;

public record ObjectHead(
        String key,
        long size,
        String etag,
        String contentType,
        String lastModified,
        Map<String, String> metadata,
        Map<String, String> tags
) {}
