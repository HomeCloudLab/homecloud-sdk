package com.homecloudlab.sdk;

public class NotConfiguredException extends HomeCloudException {
    public NotConfiguredException() {
        super("Access Key not configured. Pass accessKeyId/secretAccessKey, set HOMECLOUD_ACCESS_KEY_ID / HC_ACCESS_KEY_ID, or run HomeCloudAuth.configure(...)");
    }
}
