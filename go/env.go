package homecloud

import (
	"os"
	"strings"
	"time"
)

const (
	DefaultApex    = "holab.abrdns.com"
	DefaultProfile = "default"

	whoamiPath            = "/access-key/whoami"
	whoamiAccountSentinel = "-"
	maxRetries            = 2
	mqBatchMax            = 10
	defaultSOWorkers      = 10
)

var defaultRequestTimeout = 30 * time.Second

func envFirst(names ...string) string {
	for _, name := range names {
		if v := strings.TrimSpace(os.Getenv(name)); v != "" {
			return v
		}
	}
	return ""
}

func envProfile() string { return envFirst("HOMECLOUD_PROFILE", "HC_PROFILE") }

func envApex() string {
	v := envFirst("HOMECLOUD_APEX", "HC_APEX")
	return strings.TrimRight(v, "/")
}

func envAccountID() string {
	return envFirst("HOMECLOUD_ACCOUNT_ID", "HC_ACCOUNT_ID")
}

func envAccessKeyID() string {
	return envFirst("HOMECLOUD_ACCESS_KEY_ID", "HC_ACCESS_KEY_ID")
}

func envSecretAccessKey() string {
	return envFirst("HOMECLOUD_SECRET_ACCESS_KEY", "HC_SECRET_ACCESS_KEY")
}

func envConfigDir() string {
	return envFirst("HOMECLOUD_CONFIG_DIR", "HC_CONFIG_DIR")
}

func envCredentialsFile() string {
	return envFirst("HOMECLOUD_CREDENTIALS_FILE", "HC_CREDENTIALS_FILE")
}

func envSessionFile() string {
	return envFirst("HOMECLOUD_SESSION_FILE", "HC_SESSION_FILE")
}

func platformApex() string {
	if v := envApex(); v != "" {
		return v
	}
	return DefaultApex
}

func consoleURL(apex string) string {
	return "https://console." + apex + "/api/v1"
}

func soURL(apex string) string      { return "https://so." + apex }
func mqURL(apex string) string      { return "https://mq." + apex }
func secretsURL(apex string) string { return "https://secrets." + apex }
func mailAPIURL(apex string) string { return "https://mailapi." + apex }

func functionURL(name, apex string) string {
	return "https://" + strings.ToLower(strings.TrimSpace(name)) + ".func." + apex
}
