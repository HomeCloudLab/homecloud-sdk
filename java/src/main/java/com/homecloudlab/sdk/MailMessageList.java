package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record MailMessageList(
        List<MailMessage> items,
        @JsonProperty("next_cursor") String nextCursor,
        @JsonProperty("has_more") boolean hasMore
) {}
