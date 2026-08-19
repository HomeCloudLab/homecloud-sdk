package com.homecloudlab.sdk;

public class UnauthorizedException extends ApiException {
    UnauthorizedException(String message, int statusCode, Object detail) {
        super(message, statusCode, detail);
    }
}
