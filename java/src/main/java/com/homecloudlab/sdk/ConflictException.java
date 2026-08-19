package com.homecloudlab.sdk;

public class ConflictException extends ApiException {
    ConflictException(String message, int statusCode, Object detail) {
        super(message, statusCode, detail);
    }
}
