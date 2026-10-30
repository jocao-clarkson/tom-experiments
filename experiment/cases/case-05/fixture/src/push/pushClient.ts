import type { Platform } from "../devices/deviceRepo";

export interface PushPayload {
  title: string;
  body: string;
  data: Record<string, string>;
}

export type SendResult =
  | { ok: true }
  | { ok: false; invalidToken: true }
  | { ok: false; invalidToken: false; retryable: boolean; status: number };

/**
 * Thin wrapper over the push gateway, which fans out to APNs and FCM.
 * Each call delivers to exactly one device token.
 */
export class PushClient {
  constructor(
    private readonly gatewayUrl: string,
    private readonly apiKey: string,
    private readonly timeoutMs: number,
  ) {}

  async send(platform: Platform, token: string, payload: PushPayload): Promise<SendResult> {
    let res: Response;
    try {
      res = await fetch(`${this.gatewayUrl}/v1/send`, {
        method: "POST",
        headers: { authorization: `Bearer ${this.apiKey}`, "content-type": "application/json" },
        body: JSON.stringify({ platform, token, payload }),
        signal: AbortSignal.timeout(this.timeoutMs),
      });
    } catch {
      return { ok: false, invalidToken: false, retryable: true, status: 0 };
    }
    if (res.ok) return { ok: true };
    if (res.status === 410 || res.status === 404) return { ok: false, invalidToken: true };
    return { ok: false, invalidToken: false, retryable: res.status >= 500 || res.status === 429, status: res.status };
  }
}
