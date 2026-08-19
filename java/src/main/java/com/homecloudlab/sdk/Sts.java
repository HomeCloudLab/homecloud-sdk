package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Sts(
        @JsonProperty("access_key_id") String accessKeyId,
        @JsonProperty("secret_access_key") String secretAccessKey,
        @JsonProperty("session_token") String sessionToken,
        @JsonProperty("base_url") String baseUrl,
        @JsonProperty("mail_base_url") String mailBaseUrl,
        @JsonProperty("resource_type") String resourceType
) {}
