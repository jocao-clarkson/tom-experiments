import type { Pool } from "pg";

export interface Preferences {
  notifications: {
    orderUpdates: boolean;
    marketing: boolean;
  };
}

const DEFAULTS: Preferences = { notifications: { orderUpdates: true, marketing: false } };

export class PreferencesRepo {
  constructor(private readonly db: Pool) {}

  async get(userId: string): Promise<Preferences> {
    const res = await this.db.query(`SELECT prefs FROM user_preferences WHERE user_id = $1`, [userId]);
    if (res.rowCount === 0) return DEFAULTS;
    const stored = res.rows[0].prefs ?? {};
    return { notifications: { ...DEFAULTS.notifications, ...(stored.notifications ?? {}) } };
  }
}
