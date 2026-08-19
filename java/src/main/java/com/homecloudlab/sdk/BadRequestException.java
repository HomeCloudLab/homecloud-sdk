package com.homecloudlab.sdk;

public class BadRequestException extends ApiException {
    BadRequestException(String message, int statusCode, Object detail) {
        super(message, statusCode, detail);
    }
}
