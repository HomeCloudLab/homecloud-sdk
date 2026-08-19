package com.homecloudlab.sdk;

public class NotLoggedInException extends HomeCloudException {
    public NotLoggedInException() {
        super("This operation needs a console JWT (human session). For automation use Access Key data-plane APIs instead. Interactive: HomeCloudAuth.login(...) or homecloud login");
    }
}
