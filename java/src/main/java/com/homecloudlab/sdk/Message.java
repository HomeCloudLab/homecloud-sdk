package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Message(long sequence, String body, Map<String, String> headers, String id) {}
