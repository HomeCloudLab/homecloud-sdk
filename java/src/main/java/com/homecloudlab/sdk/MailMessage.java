package com.homecloudlab.sdk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record MailMessage(
        String id,
        String subject,
        @JsonProperty("mailbox_id") String mailboxId,
        @JsonProperty("body_html") String bodyHtml,
        @JsonProperty("body_text") String bodyText
) {}
