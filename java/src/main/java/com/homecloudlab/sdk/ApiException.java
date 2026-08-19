package com.homecloudlab.sdk;

public class ApiException extends HomeCloudException {
    ApiException(String message, int statusCode, Object detail) {
        super(message, statusCode, detail, null);
    }
}
