package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record PresignedUrl(
        String url,
        @JsonProperty("expires_in_seconds") int expiresInSeconds
) {}
