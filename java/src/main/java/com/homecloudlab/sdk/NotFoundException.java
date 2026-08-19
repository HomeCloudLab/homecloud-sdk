package com.homecloudlab.sdk;

public class NotFoundException extends ApiException {
    private final String resourceType;
    private final String resource;

    NotFoundException(String message, int statusCode, Object detail, String resourceType, String resource) {
        super(message, statusCode, detail);
        this.resourceType = resourceType == null ? "" : resourceType;
        this.resource = resource == null ? "" : resource;
    }

    public String getResourceType() {
        return resourceType;
    }

    public String getResource() {
        return resource;
    }
}
