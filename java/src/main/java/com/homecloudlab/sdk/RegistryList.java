package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record RegistryList(List<RegistryRepo> items) {}
