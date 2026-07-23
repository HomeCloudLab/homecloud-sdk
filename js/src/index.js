"use strict";

const { HomeCloud, AsyncHomeCloud } = require("./client");
const {
  HomeCloudError,
  NotConfiguredError,
  NotLoggedInError,
  ApiError,
  BadRequestError,
  UnauthorizedError,
  PermissionDeniedError,
  NotFoundError,
  ConflictError,
  RateLimitError,
  ServiceUnavailableError,
  errorFromStatus,
} = require("./errors");
const { signRequestHeaders, buildStringToSign, soObjectPaths } = require("./signing");
const {
  DEFAULT_APEX,
  soUrl,
  mqUrl,
  secretsUrl,
  mailApiUrl,
  consoleUrl,
  functionUrl,
} = require("./defaults");

module.exports = {
  HomeCloud,
  AsyncHomeCloud,
  HomeCloudError,
  NotConfiguredError,
  NotLoggedInError,
  ApiError,
  BadRequestError,
  UnauthorizedError,
  PermissionDeniedError,
  NotFoundError,
  ConflictError,
  RateLimitError,
  ServiceUnavailableError,
  errorFromStatus,
  signRequestHeaders,
  buildStringToSign,
  soObjectPaths,
  soUrl,
  mqUrl,
  secretsUrl,
  mailApiUrl,
  consoleUrl,
  functionUrl,
  DEFAULT_APEX,
};
