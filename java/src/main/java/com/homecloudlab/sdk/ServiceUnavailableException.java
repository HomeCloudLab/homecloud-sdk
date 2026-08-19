package com.homecloudlab.sdk;

public class ServiceUnavailableException extends ApiException {
    ServiceUnavailableException(String message, int statusCode, Object detail) {
        super(message, statusCode, detail);
    }
}
