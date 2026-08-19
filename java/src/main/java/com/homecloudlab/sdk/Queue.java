package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Queue(
        String id,
        String name,
        @JsonProperty("iam_arn") String iamArn,
        String status,
        @JsonProperty("created_at") String createdAt
) {}
