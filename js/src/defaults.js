"use strict";

const DEFAULT_APEX = "holab.abrdns.com";
const DEFAULT_PROFILE = "default";
const WHOAMI_PATH = "/access-key/whoami";
const WHOAMI_ACCOUNT_SENTINEL = "-";

function soUrl(apex) {
  return `https://so.${apex || DEFAULT_APEX}`;
}
function mqUrl(apex) {
  return `https://mq.${apex || DEFAULT_APEX}`;
}
function secretsUrl(apex) {
  return `https://secrets.${apex || DEFAULT_APEX}`;
}
function mailApiUrl(apex) {
  return `https://mailapi.${apex || DEFAULT_APEX}`;
}
function consoleUrl(apex) {
  return `https://console.${apex || DEFAULT_APEX}/api/v1`;
}
function functionUrl(name, apex) {
  return `https://${String(name).trim().toLowerCase()}.func.${apex || DEFAULT_APEX}`;
}

function envFirst(...names) {
  for (const name of names) {
    const v = process.env[name];
    if (v != null && String(v).trim() !== "") return v;
  }
  return null;
}

module.exports = {
  DEFAULT_APEX,
  DEFAULT_PROFILE,
  WHOAMI_PATH,
  WHOAMI_ACCOUNT_SENTINEL,
  soUrl,
  mqUrl,
  secretsUrl,
  mailApiUrl,
  consoleUrl,
  functionUrl,
  envFirst,
};
