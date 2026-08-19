package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ObjectListItem(
        String key,
        long size,
        @JsonProperty("is_dir") boolean isDir,
        String etag
) {}
