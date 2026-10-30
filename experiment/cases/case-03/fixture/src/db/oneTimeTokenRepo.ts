import { createHash, randomBytes } from "node:crypto";
import type { Pool } from "pg";

export type TokenPurpose = "email_verification" | "email_change";

export interface ConsumedToken {
  userId: string;
  purpose: TokenPurpose;
}

/** Tokens are stored only as SHA-256 hashes. */
export function hashToken(token: string): string {
  return createHash("sha256").update(token, "utf8").digest("hex");
}

/**
 * Single-use tokens sent to users in emailed links. The raw token is returned
 * once to the caller and only its hash is persisted.
 *
 * Table: one_time_tokens(token_hash PK, user_id, purpose, expires_at, used_at)
 */
export class OneTimeTokenRepo {
  constructor(
    private readonly db: Pool,
    private readonly ttlMinutes: number,
  ) {}

  async issue(userId: string, purpose: TokenPurpose): Promise<string> {
    const token = randomBytes(32).toString("base64url");
    await this.db.query(
      `INSERT INTO one_time_tokens (token_hash, user_id, purpose, expires_at)
       VALUES ($1, $2, $3, now() + make_interval(mins => $4))`,
      [hashToken(token), userId, purpose, this.ttlMinutes],
    );
    return token;
  }

  /** Atomically marks the token used. Returns null if unknown, expired or already used. */
  async consume(token: string, purpose: TokenPurpose): Promise<ConsumedToken | null> {
    const res = await this.db.query(
      `UPDATE one_time_tokens SET used_at = now()
        WHERE token_hash = $1 AND purpose = $2 AND used_at IS NULL AND expires_at > now()
        RETURNING user_id, purpose`,
      [hashToken(token), purpose],
    );
    if (res.rowCount === 0) return null;
    return { userId: res.rows[0].user_id, purpose: res.rows[0].purpose };
  }

  /** Invalidates every outstanding token of a purpose for a user. */
  async revokeAll(userId: string, purpose: TokenPurpose): Promise<void> {
    await this.db.query(
      `UPDATE one_time_tokens SET used_at = now()
        WHERE user_id = $1 AND purpose = $2 AND used_at IS NULL`,
      [userId, purpose],
    );
  }
}
