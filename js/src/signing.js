"use strict";

const crypto = require("crypto");

function buildStringToSign({ method, path: reqPath, timestamp, accountId }) {
  return `${String(method).toUpperCase()}\n${reqPath}\n${timestamp}\n${accountId}`;
}

function signRequestHeaders({
  accessKeyId,
  secret,
  method,
  path: reqPath,
  accountId,
  sessionToken,
}) {
  const timestamp = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const stringToSign = buildStringToSign({
    method,
    path: reqPath,
    timestamp,
    accountId,
  });
  const signature = crypto.createHmac("sha256", secret).update(stringToSign).digest("hex");
  const headers = {
    "X-Homecloud-Access-Key-Id": accessKeyId,
    "X-Homecloud-Date": timestamp,
    "X-Homecloud-Signature": signature,
  };
  if (sessionToken) headers["X-Homecloud-Session-Token"] = sessionToken;
  return headers;
}

function encodeObjectKeyPath(key) {
  return key
    .replace(/^\/+/, "")
    .split("/")
    .map((part) => encodeURIComponent(part))
    .join("/");
}

function soObjectPaths(accountId, bucketName, objectKey) {
  const key = String(objectKey || "").replace(/^\/+/, "");
  const signPath = `/${accountId}/${bucketName}/objects/${key}`;
  const urlPath = `/${accountId}/${bucketName}/objects/${encodeObjectKeyPath(key)}`;
  return { signPath, urlPath };
}

module.exports = {
  buildStringToSign,
  signRequestHeaders,
  encodeObjectKeyPath,
  soObjectPaths,
};
