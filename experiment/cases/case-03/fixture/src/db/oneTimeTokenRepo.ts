import type { Pool } from "pg";
import { generateToken, hashToken } from "../crypto/tokens.js";

export type TokenPurpose = "email_verification" | "email_change";

const TOKEN_TTL_MS = 24 * 60 * 60 * 1000;

export interface ConsumedToken {
  userId: string;
  purpose: TokenPurpose;
}

/**
 * Single-use tokens sent to users by email. The raw token is returned once to
 * the caller and only its hash is persisted.
 *
 * Table: one_time_tokens(token_hash PK, user_id, purpose, expires_at, used_at)
 */
export class OneTimeTokenRepo {
  constructor(private readonly db: Pool) {}

  async issue(userId: string, purpose: TokenPurpose): Promise<string> {
    const token = generateToken();
    await this.db.query(
      `INSERT INTO one_time_tokens (token_hash, user_id, purpose, expires_at)
       VALUES ($1, $2, $3, now() + ($4 || ' milliseconds')::interval)`,
      [hashToken(token), userId, purpose, String(TOKEN_TTL_MS)],
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
