package com.homecloudlab.sdk;

public final class ListObjectsOptions {
    private final String prefix;
    private final boolean recursive;
    private final int page;
    private final int pageSize;
    private final String continuationToken;

    private ListObjectsOptions(Builder b) {
        this.prefix = b.prefix == null ? "" : b.prefix;
        this.recursive = b.recursive;
        this.page = b.page;
        this.pageSize = b.pageSize;
        this.continuationToken = b.continuationToken == null ? "" : b.continuationToken;
    }

    public static Builder builder() {
        return new Builder();
    }

    public String prefix() { return prefix; }
    public boolean recursive() { return recursive; }
    public int page() { return page; }
    public int pageSize() { return pageSize; }
    public String continuationToken() { return continuationToken; }

    public static final class Builder {
        private String prefix = "";
        private boolean recursive;
        private int page;
        private int pageSize;
        private String continuationToken = "";

        public Builder prefix(String prefix) { this.prefix = prefix; return this; }
        public Builder recursive(boolean recursive) { this.recursive = recursive; return this; }
        public Builder page(int page) { this.page = page; return this; }
        public Builder pageSize(int pageSize) { this.pageSize = pageSize; return this; }
        public Builder continuationToken(String continuationToken) { this.continuationToken = continuationToken; return this; }
        public ListObjectsOptions build() { return new ListObjectsOptions(this); }
    }
}
