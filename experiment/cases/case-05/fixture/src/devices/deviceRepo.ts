import type { Pool } from "pg";

export type Platform = "ios" | "android";

export interface Device {
  token: string;
  userId: string;
  platform: Platform;
  appVersion: string;
  createdAt: Date;
  lastSeenAt: Date;
}

export class DeviceRepo {
  constructor(private readonly db: Pool) {}

  /**
   * Registers a push token. A token is unique across users: if the same
   * physical device signs in as a different user, the token moves to them.
   */
  async upsertByToken(d: Omit<Device, "createdAt" | "lastSeenAt">): Promise<void> {
    await this.db.query(
      `INSERT INTO devices (token, user_id, platform, app_version, created_at, last_seen_at)
       VALUES ($1, $2, $3, $4, now(), now())
       ON CONFLICT (token) DO UPDATE
         SET user_id = EXCLUDED.user_id, platform = EXCLUDED.platform,
             app_version = EXCLUDED.app_version, last_seen_at = now()`,
      [d.token, d.userId, d.platform, d.appVersion],
    );
  }

  async listForUser(userId: string): Promise<Device[]> {
    const res = await this.db.query(
      `SELECT token, user_id, platform, app_version, created_at, last_seen_at
         FROM devices WHERE user_id = $1 ORDER BY last_seen_at DESC`,
      [userId],
    );
    return res.rows.map((r) => ({
      token: r.token,
      userId: r.user_id,
      platform: r.platform,
      appVersion: r.app_version,
      createdAt: r.created_at,
      lastSeenAt: r.last_seen_at,
    }));
  }

  async deleteByToken(token: string, userId?: string): Promise<number> {
    const res = userId
      ? await this.db.query(`DELETE FROM devices WHERE token = $1 AND user_id = $2`, [token, userId])
      : await this.db.query(`DELETE FROM devices WHERE token = $1`, [token]);
    return res.rowCount ?? 0;
  }
}
