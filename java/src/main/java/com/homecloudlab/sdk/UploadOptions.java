package com.homecloudlab.sdk;

public final class UploadOptions {
    private final String filePath;
    private final byte[] body;
    private final String key;
    private final String contentType;

    private UploadOptions(Builder b) {
        this.filePath = b.filePath;
        this.body = b.body;
        this.key = b.key;
        this.contentType = b.contentType;
    }

    public static Builder builder() {
        return new Builder();
    }

    public String filePath() { return filePath; }
    public byte[] body() { return body; }
    public String key() { return key; }
    public String contentType() { return contentType; }

    public static final class Builder {
        private String filePath;
        private byte[] body;
        private String key;
        private String contentType;

        public Builder filePath(String filePath) { this.filePath = filePath; return this; }
        public Builder body(byte[] body) { this.body = body; return this; }
        public Builder key(String key) { this.key = key; return this; }
        public Builder contentType(String contentType) { this.contentType = contentType; return this; }
        public UploadOptions build() { return new UploadOptions(this); }
    }
}
