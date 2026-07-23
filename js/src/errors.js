"use strict";

class HomeCloudError extends Error {
  constructor(message, { statusCode = null, detail = null } = {}) {
    super(message);
    this.name = "HomeCloudError";
    this.statusCode = statusCode;
    this.detail = detail;
  }

  get errorPayload() {
    if (!this.detail || typeof this.detail !== "object") return null;
    const error = this.detail.error;
    if (error && typeof error === "object" && error.code) {
      return {
        code: String(error.code),
        message: String(error.message || error.code),
        details: error.details && typeof error.details === "object" ? error.details : {},
      };
    }
    if (this.detail.code) {
      const details = { ...this.detail };
      delete details.code;
      delete details.message;
      return {
        code: String(this.detail.code),
        message: String(this.detail.message || this.detail.code),
        details,
      };
    }
    return null;
  }

  get errorCode() {
    const p = this.errorPayload;
    return p ? p.code : null;
  }
}

class NotConfiguredError extends HomeCloudError {
  constructor(message, opts) {
    super(message, opts);
    this.name = "NotConfiguredError";
  }
}

class NotLoggedInError extends HomeCloudError {
  constructor(message, opts) {
    super(message || "Not logged in. Run: homecloud login", opts);
    this.name = "NotLoggedInError";
  }
}

class ApiError extends HomeCloudError {
  constructor(message, opts) {
    super(message, opts);
    this.name = "ApiError";
  }
}

class BadRequestError extends ApiError {
  constructor(message, opts) {
    super(message, opts);
    this.name = "BadRequestError";
  }
}

class UnauthorizedError extends ApiError {
  constructor(message, opts) {
    super(message, opts);
    this.name = "UnauthorizedError";
  }
}

class PermissionDeniedError extends ApiError {
  constructor(message, opts) {
    super(message, opts);
    this.name = "PermissionDeniedError";
  }
}

class NotFoundError extends ApiError {
  constructor(message, opts = {}) {
    super(message, { statusCode: 404, ...opts });
    this.name = "NotFoundError";
    this.resourceType = opts.resourceType || null;
    this.resource = opts.resource || null;
  }
}

class ConflictError extends ApiError {
  constructor(message, opts) {
    super(message, opts);
    this.name = "ConflictError";
  }
}

class RateLimitError extends ApiError {
  constructor(message, opts) {
    super(message, opts);
    this.name = "RateLimitError";
  }
}

class ServiceUnavailableError extends ApiError {
  constructor(message, opts) {
    super(message, opts);
    this.name = "ServiceUnavailableError";
  }
}

function detailMessage(detail) {
  if (detail == null) return null;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (typeof detail === "object" && !Array.isArray(detail)) {
    if (detail.error && typeof detail.error === "object") {
      return String(detail.error.message || detail.error.code || "");
    }
    if (detail.message) return String(detail.message);
    if (detail.code) return String(detail.code);
  }
  return null;
}

function errorFromStatus(statusCode, { detail = null, url = null } = {}) {
  const apiMsg = detailMessage(detail);
  if (statusCode === 400) return new BadRequestError(apiMsg || "Bad request", { statusCode, detail });
  if (statusCode === 401) {
    return new UnauthorizedError(apiMsg || "Unauthorized — check Access Key or console session", {
      statusCode,
      detail,
    });
  }
  if (statusCode === 403) {
    return new PermissionDeniedError(apiMsg || "Permission denied", { statusCode, detail });
  }
  if (statusCode === 404) {
    return new NotFoundError(apiMsg || "Resource not found", { statusCode, detail });
  }
  if (statusCode === 409) return new ConflictError(apiMsg || "Conflict", { statusCode, detail });
  if (statusCode === 429) {
    return new RateLimitError(apiMsg || "Rate limit exceeded", { statusCode, detail });
  }
  if ([502, 503, 504].includes(statusCode)) {
    return new ServiceUnavailableError(apiMsg || `Service unavailable (${statusCode})`, {
      statusCode,
      detail,
    });
  }
  return new ApiError(apiMsg || `Request failed (${statusCode})`, { statusCode, detail });
}

module.exports = {
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
};
