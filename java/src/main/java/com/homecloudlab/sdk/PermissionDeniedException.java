package com.homecloudlab.sdk;

public class PermissionDeniedException extends ApiException {
    PermissionDeniedException(String message, int statusCode, Object detail) {
        super(message, statusCode, detail);
    }
}
