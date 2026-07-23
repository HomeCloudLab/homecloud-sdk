"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const { DEFAULT_APEX, DEFAULT_PROFILE, envFirst } = require("./defaults");

function homecloudDir() {
  const override = envFirst("HOMECLOUD_CONFIG_DIR", "HC_CONFIG_DIR");
  if (override) return path.resolve(override.replace(/^~(?=\/|\\)/, os.homedir()));
  return path.join(os.homedir(), ".homecloud");
}

function credentialsPath() {
  const override = envFirst("HOMECLOUD_CREDENTIALS_FILE", "HC_CREDENTIALS_FILE");
  if (override) return path.resolve(override.replace(/^~(?=\/|\\)/, os.homedir()));
  return path.join(homecloudDir(), "credentials");
}

function sessionPath() {
  const override = envFirst("HOMECLOUD_SESSION_FILE", "HC_SESSION_FILE");
  if (override) return path.resolve(override.replace(/^~(?=\/|\\)/, os.homedir()));
  return path.join(homecloudDir(), "session");
}

function loadCredentials(filePath = credentialsPath()) {
  if (!fs.existsSync(filePath)) {
    return { version: 2, default_profile: DEFAULT_PROFILE, profiles: {} };
  }
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
  if (!raw || typeof raw !== "object") throw new Error("Invalid credentials file");
  if (raw.profiles && typeof raw.profiles === "object") {
    return {
      version: Number(raw.version || 2),
      default_profile: raw.default_profile || DEFAULT_PROFILE,
      profiles: raw.profiles,
    };
  }
  // legacy flat
  return {
    version: 2,
    default_profile: DEFAULT_PROFILE,
    profiles: { [DEFAULT_PROFILE]: raw },
  };
}

function loadSession(filePath = sessionPath()) {
  if (!fs.existsSync(filePath)) return { version: 1, profiles: {} };
  const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));
  return {
    version: Number(raw.version || 1),
    profiles: raw.profiles || {},
  };
}

function saveSession(session, filePath = sessionPath()) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(session, null, 2) + "\n", "utf8");
  try {
    fs.chmodSync(filePath, 0o600);
  } catch (_) {}
  return filePath;
}

function resolveProfile(name) {
  const creds = loadCredentials();
  const profileName =
    name ||
    envFirst("HOMECLOUD_PROFILE", "HC_PROFILE") ||
    creds.default_profile ||
    DEFAULT_PROFILE;
  const profile = creds.profiles[profileName] || {};
  const session = loadSession().profiles[profileName] || {};
  return {
    profileName,
    apex: envFirst("HOMECLOUD_APEX", "HC_APEX") || profile.apex || DEFAULT_APEX,
    accountId:
      envFirst("HOMECLOUD_ACCOUNT_ID", "HC_ACCOUNT_ID") ||
      profile.default_account_id ||
      session.active_account_id ||
      null,
    accessKeyId:
      envFirst("HOMECLOUD_ACCESS_KEY_ID", "HC_ACCESS_KEY_ID") || profile.access_key_id || null,
    secretAccessKey:
      envFirst("HOMECLOUD_SECRET_ACCESS_KEY", "HC_SECRET_ACCESS_KEY") ||
      profile.secret_access_key ||
      null,
    accessToken: session.access_token || null,
  };
}

module.exports = {
  homecloudDir,
  credentialsPath,
  sessionPath,
  loadCredentials,
  loadSession,
  saveSession,
  resolveProfile,
};
