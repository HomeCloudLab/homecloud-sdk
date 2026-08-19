package com.homecloudlab.sdk;

import java.util.List;

public final class Accounts {
    private final HomeCloud c;

    Accounts(HomeCloud c) {
        this.c = c;
    }

    public List<Account> list() {
        return Json.itemsOf(c.consoleJson("GET", "accounts", true, null, null, null, null), Account.class);
    }

    /** Resolves account id on this client (whoami-style mutation of the resolved account only). */
    public void switchTo(String accountRef) {
        List<Account> accounts = list();
        Account match = null;
        for (Account acc : accounts) {
            if (accountRef.equals(acc.id()) || accountRef.equals(acc.slug()) || accountRef.equals(acc.name())) {
                match = acc;
                break;
            }
        }
        if (match == null) {
            throw new HomeCloudException("Account not found: " + accountRef);
        }
        c.setAccountId(match.id());
    }
}
