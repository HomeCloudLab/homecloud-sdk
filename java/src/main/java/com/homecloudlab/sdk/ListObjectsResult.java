package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ListObjectsResult(
        List<ObjectListItem> items,
        @JsonProperty("has_more") boolean hasMore,
        @JsonProperty("next_continuation_token") String nextContinuationToken,
        Integer pages
) {
    public List<ObjectListItem> items() {
        return items == null ? List.of() : items;
    }
}
