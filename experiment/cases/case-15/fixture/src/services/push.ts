import { query } from "../db/pool";

export interface PushPayload {
  title: string;
  body: string;
  data?: Record<string, string>;
}

export interface PushProvider {
  sendMulticast(tokens: string[], payload: PushPayload): Promise<{ failedTokens: string[] }>;
}

const BATCH = 500;

export class PushService {
  constructor(private readonly provider: PushProvider) {}

  async sendToUser(userId: string, payload: PushPayload): Promise<void> {
    const { rows } = await query<{ token: string }>(
      "SELECT token FROM device_tokens WHERE user_id = $1 AND revoked_at IS NULL",
      [userId],
    );
    const tokens = rows.map((r) => r.token);
    for (let i = 0; i < tokens.length; i += BATCH) {
      const { failedTokens } = await this.provider.sendMulticast(tokens.slice(i, i + BATCH), payload);
      if (failedTokens.length) {
        await query("UPDATE device_tokens SET revoked_at = now() WHERE token = ANY($1)", [failedTokens]);
      }
    }
  }
}
