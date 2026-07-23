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
  statusCode?: number;
  detail?: unknown;
  constructor(message: string, opts?: { statusCode?: number; detail?: unknown });
}

export declare class HomeCloud {
  so: {
    upload(bucketName: string, filePath: string, opts?: { key?: string }): Promise<unknown>;
    putJson(bucketName: string, objectKey: string, value: unknown): Promise<unknown>;
  };
  mq: {
    send(queueName: string, body: unknown, opts?: { headers?: Record<string, string> }): Promise<unknown>;
  };
  secrets: {
    get(secretName: string): Promise<unknown>;
  };
  mail: {
    listMessages(opts?: { mailbox?: string; limit?: number }): Promise<unknown>;
  };
  static fromSts(sts: StsEntry, opts?: { accountId?: string; apex?: string }): HomeCloud;
  static fromFunctionContext(context: Record<string, unknown>, opts: { binding: string }): HomeCloud;
}

export declare const DEFAULT_APEX: string;
