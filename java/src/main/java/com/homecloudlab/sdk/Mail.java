package com.homecloudlab.sdk;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class Mail {
    private final HomeCloud c;

    Mail(HomeCloud c) {
        this.c = c;
    }

    private byte[] request(String method, String path, Map<String, String> q) {
        c.ensureAccountId();
        if (c.hasAccessKey() && c.hasMailDataPlaneOverride()) {
            String dp = mailConsolePathToDataPlane(path, c.accountIdOrEmpty());
            return c.dataPlaneJson("mail", method, dp, "", q, null, null);
        }
        if (c.hasAccessKey()) {
            return c.consoleSignedJson(method, path, c.accountIdOrEmpty(), q);
        }
        return c.consoleJson(method, path, true, null, q, null, null);
    }

    public List<Mailbox> listMailboxes() {
        c.ensureAccountId();
        return Json.itemsOf(request("GET", "accounts/" + c.accountIdOrEmpty() + "/mail/mailboxes", null), Mailbox.class);
    }

    public MailMessageList listMessages(ListMessagesOptions opts) {
        c.ensureAccountId();
        if (opts == null) {
            opts = ListMessagesOptions.builder().build();
        }
        int limit = opts.limit() <= 0 ? 50 : opts.limit();
        Map<String, String> q = new LinkedHashMap<>();
        q.put("limit", Integer.toString(limit));
        putIf(q, "mailbox_id", opts.mailboxId());
        putIf(q, "folder", opts.folder());
        putIf(q, "direction", opts.direction());
        putIf(q, "status", opts.status());
        putIf(q, "search", opts.search());
        putIf(q, "cursor", opts.cursor());
        byte[] raw = request("GET", "accounts/" + c.accountIdOrEmpty() + "/mail/messages", q);
        MailMessageList list = Json.decode(raw, MailMessageList.class);
        return list == null ? new MailMessageList(List.of(), "", false) : list;
    }

    public MailMessage getMessage(String messageId) {
        c.ensureAccountId();
        return Json.decode(request("GET", "accounts/" + c.accountIdOrEmpty() + "/mail/messages/" + messageId, null), MailMessage.class);
    }

    public byte[] downloadAttachment(String messageId, String partId) {
        c.ensureAccountId();
        return request("GET", "accounts/" + c.accountIdOrEmpty() + "/mail/messages/" + messageId + "/attachments/" + partId, null);
    }

    private static void putIf(Map<String, String> q, String k, String v) {
        if (v != null && !v.isEmpty()) {
            q.put(k, v);
        }
    }

    static String mailConsolePathToDataPlane(String path, String accountId) {
        String p = path;
        while (p.startsWith("/")) {
            p = p.substring(1);
        }
        String prefix = "accounts/" + accountId + "/mail/";
        if (p.startsWith(prefix)) {
            return "/" + accountId + "/" + p.substring(prefix.length());
        }
        if (p.startsWith(accountId + "/")) {
            return "/" + p;
        }
        return "/" + p;
    }
}
