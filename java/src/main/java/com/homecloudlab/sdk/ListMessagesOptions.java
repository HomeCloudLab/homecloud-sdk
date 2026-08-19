package com.homecloudlab.sdk;

public final class ListMessagesOptions {
    private final String mailboxId;
    private final String folder;
    private final String direction;
    private final String status;
    private final String search;
    private final int limit;
    private final String cursor;

    private ListMessagesOptions(Builder b) {
        this.mailboxId = b.mailboxId;
        this.folder = b.folder;
        this.direction = b.direction;
        this.status = b.status;
        this.search = b.search;
        this.limit = b.limit;
        this.cursor = b.cursor;
    }

    public static Builder builder() {
        return new Builder();
    }

    public String mailboxId() { return mailboxId; }
    public String folder() { return folder; }
    public String direction() { return direction; }
    public String status() { return status; }
    public String search() { return search; }
    public int limit() { return limit; }
    public String cursor() { return cursor; }

    public static final class Builder {
        private String mailboxId = "";
        private String folder = "";
        private String direction = "";
        private String status = "";
        private String search = "";
        private int limit;
        private String cursor = "";

        public Builder mailboxId(String v) { this.mailboxId = v; return this; }
        public Builder folder(String v) { this.folder = v; return this; }
        public Builder direction(String v) { this.direction = v; return this; }
        public Builder status(String v) { this.status = v; return this; }
        public Builder search(String v) { this.search = v; return this; }
        public Builder limit(int v) { this.limit = v; return this; }
        public Builder cursor(String v) { this.cursor = v; return this; }
        public ListMessagesOptions build() { return new ListMessagesOptions(this); }
    }
}
