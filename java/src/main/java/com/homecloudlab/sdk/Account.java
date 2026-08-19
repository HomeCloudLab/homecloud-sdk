package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Account(String id, String slug, String name) {}
