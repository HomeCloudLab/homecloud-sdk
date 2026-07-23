export type StsEntry = {
  access_key_id: string;
  secret_access_key: string;
  session_token?: string;
  base_url?: string;
  mail_base_url?: string;
  resource_type?: string;
  resource_name?: string;
};

export declare class HomeCloudError extends Error {
  statusCode?: number | null;
  detail?: unknown;
  constructor(message: string, opts?: { statusCode?: number | null; detail?: unknown });
}

export declare class NotConfiguredError extends HomeCloudError {}
export declare class NotLoggedInError extends HomeCloudError {}
export declare class ApiError extends HomeCloudError {}
export declare class BadRequestError extends ApiError {}
export declare class UnauthorizedError extends ApiError {}
export declare class PermissionDeniedError extends ApiError {}
export declare class NotFoundError extends ApiError {
  resourceType?: string | null;
  resource?: string | null;
}
export declare class ConflictError extends ApiError {}
export declare class RateLimitError extends ApiError {}
export declare class ServiceUnavailableError extends ApiError {}

export declare class HomeCloud {
  so: any;
  storage: any;
  mq: any;
  secrets: any;
  mail: any;
  accounts: any;
  apps: any;
  queues: any;
  functions: any;
  accountId: string | null;
  accessToken: string | null;
  constructor(opts?: Record<string, unknown>);
  static fromEnv(opts?: Record<string, unknown>): HomeCloud;
  static fromProfile(profile?: string | null, opts?: Record<string, unknown>): HomeCloud;
  static fromCredentials(
    accessKeyId: string,
    secretAccessKey: string,
    opts?: Record<string, unknown>
  ): HomeCloud;
  static fromSts(sts: StsEntry, opts?: { accountId?: string; apex?: string }): HomeCloud;
  static fromFunctionContext(
    context: Record<string, unknown>,
    opts: { binding: string }
  ): HomeCloud;
  ensureAccountId(): Promise<string>;
  login(username: string, password: string, opts?: { mfaCode?: string }): Promise<void>;
  loginBrowser(opts?: {
    openBrowser?: boolean;
    onWaiting?: (uri: string) => void;
    mfaToken?: string;
  }): Promise<void>;
}

export declare const AsyncHomeCloud: typeof HomeCloud;
export declare const DEFAULT_APEX: string;
export declare function signRequestHeaders(opts: Record<string, unknown>): Record<string, string>;
