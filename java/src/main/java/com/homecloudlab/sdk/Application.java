package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Application(String id, String name, String slug, String status) {}
