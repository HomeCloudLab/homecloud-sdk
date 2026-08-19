package homecloud

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

type profileConfig struct {
	Name             string
	Apex             string
	DefaultAccountID string
	AccessKeyID      string
	SecretAccessKey  string
}

type credentialsFile struct {
	Version        int
	DefaultProfile string
	Profiles       map[string]profileConfig
}

type profileSession struct {
	AccessToken       string
	ActiveAccountID   string
	LastUsedAccountID string
}

func homecloudDir() string {
	if override := envConfigDir(); override != "" {
		return expandHome(override)
	}
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".homecloud")
}

func credentialsPath() string {
	if override := envCredentialsFile(); override != "" {
		return expandHome(override)
	}
	return filepath.Join(homecloudDir(), "credentials")
}

func sessionPath() string {
	if override := envSessionFile(); override != "" {
		return expandHome(override)
	}
	return filepath.Join(homecloudDir(), "session")
}

func expandHome(p string) string {
	if strings.HasPrefix(p, "~/") || strings.HasPrefix(p, "~\\") {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, p[2:])
	}
	return p
}

func loadCredentialsFile(path string) (*credentialsFile, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var data map[string]any
	if err := json.Unmarshal(raw, &data); err != nil {
		return nil, err
	}
	normalized := normalizeCredentials(data)
	out := &credentialsFile{
		Version:        jsonInt(normalized["version"], 2),
		DefaultProfile: jsonString(normalized["default_profile"], DefaultProfile),
		Profiles:       map[string]profileConfig{},
	}
	profiles, _ := normalized["profiles"].(map[string]any)
	for name, p := range profiles {
		pm, _ := p.(map[string]any)
		out.Profiles[name] = profileConfig{
			Name:             name,
			Apex:             jsonString(pm["apex"], platformApex()),
			DefaultAccountID: jsonString(pm["default_account_id"], ""),
			AccessKeyID:      jsonString(pm["access_key_id"], ""),
			SecretAccessKey:  jsonString(pm["secret_access_key"], ""),
		}
	}
	if len(out.Profiles) == 0 {
		return nil, newError("No profiles found in credentials file")
	}
	return out, nil
}

func normalizeCredentials(data map[string]any) map[string]any {
	if _, ok := data["profiles"]; ok {
		return data
	}
	return map[string]any{
		"version":         data["version"],
		"default_profile": DefaultProfile,
		"profiles":        map[string]any{DefaultProfile: data},
	}
}

func saveCredentialsFile(cf *credentialsFile, path string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	profiles := map[string]any{}
	for name, p := range cf.Profiles {
		profiles[name] = map[string]any{
			"access_key_id":     p.AccessKeyID,
			"secret_access_key": p.SecretAccessKey,
		}
	}
	payload := map[string]any{
		"version":         cf.Version,
		"default_profile": cf.DefaultProfile,
		"profiles":        profiles,
	}
	raw, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o600)
}

func loadSessionFile(path string) map[string]profileSession {
	out := map[string]profileSession{}
	raw, err := os.ReadFile(path)
	if err != nil {
		return out
	}
	var data struct {
		Profiles map[string]map[string]string `json:"profiles"`
	}
	if json.Unmarshal(raw, &data) != nil {
		return out
	}
	for name, p := range data.Profiles {
		out[name] = profileSession{
			AccessToken:       p["access_token"],
			ActiveAccountID:   p["active_account_id"],
			LastUsedAccountID: p["last_used_account_id"],
		}
	}
	return out
}

func saveSessionFile(path string, profiles map[string]profileSession) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	payloadProfiles := map[string]any{}
	for name, p := range profiles {
		if p.AccessToken == "" && p.ActiveAccountID == "" && p.LastUsedAccountID == "" {
			continue
		}
		entry := map[string]any{}
		if p.AccessToken != "" {
			entry["access_token"] = p.AccessToken
		}
		if p.ActiveAccountID != "" {
			entry["active_account_id"] = p.ActiveAccountID
		}
		if p.LastUsedAccountID != "" {
			entry["last_used_account_id"] = p.LastUsedAccountID
		}
		payloadProfiles[name] = entry
	}
	payload := map[string]any{"version": 1, "profiles": payloadProfiles}
	raw, err := json.MarshalIndent(payload, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(path, raw, 0o600)
}

func jsonString(v any, fallback string) string {
	s, _ := v.(string)
	s = strings.TrimSpace(s)
	if s == "" {
		return fallback
	}
	return strings.TrimRight(s, "/")
}

func jsonInt(v any, fallback int) int {
	switch t := v.(type) {
	case float64:
		return int(t)
	case int:
		return t
	default:
		return fallback
	}
}
