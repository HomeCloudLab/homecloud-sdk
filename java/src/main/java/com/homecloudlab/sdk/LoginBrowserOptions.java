package com.homecloudlab.sdk;

import java.time.Duration;
import java.util.function.Consumer;

public record LoginBrowserOptions(boolean openBrowser, String mfaToken, Consumer<String> onWaiting, Duration pollEvery) {
    public static LoginBrowserOptions defaults() {
        return new LoginBrowserOptions(true, "", null, Duration.ZERO);
    }
}
