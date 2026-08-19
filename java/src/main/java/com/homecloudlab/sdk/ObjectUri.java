package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record ObjectUri(
        @JsonProperty("so_uri") String soUri,
        @JsonProperty("https_url") String httpsUrl,
        @JsonProperty("https_requires_public") boolean httpsRequiresPublic
) {}
