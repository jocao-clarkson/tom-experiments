import type { Pool } from "pg";
import type { Session, SessionRepo, User, UserRepo } from "./types.js";

export class PgUserRepo implements UserRepo {
  constructor(private readonly pool: Pool) {}

  async findByEmail(email: string): Promise<User | null> {
    const r = await this.pool.query(
      "SELECT id, email, password_hash FROM users WHERE lower(email) = lower($1)",
      [email],
    );
    return r.rows[0] ? toUser(r.rows[0]) : null;
  }

  async findById(id: string): Promise<User | null> {
    const r = await this.pool.query("SELECT id, email, password_hash FROM users WHERE id = $1", [id]);
    return r.rows[0] ? toUser(r.rows[0]) : null;
  }

  async updatePasswordHash(userId: string, hash: string): Promise<void> {
    await this.pool.query("UPDATE users SET password_hash = $2, updated_at = now() WHERE id = $1", [userId, hash]);
  }
}

export class PgSessionRepo implements SessionRepo {
  constructor(private readonly pool: Pool) {}

  async create(userId: string, tokenHash: string): Promise<Session> {
    const r = await this.pool.query(
      "INSERT INTO sessions (user_id, token_hash) VALUES ($1, $2) RETURNING id, user_id, token_hash, created_at",
      [userId, tokenHash],
    );
    const row = r.rows[0];
    return { id: row.id, userId: row.user_id, tokenHash: row.token_hash, createdAt: row.created_at };
  }

  async findByTokenHash(tokenHash: string): Promise<Session | null> {
    const r = await this.pool.query(
      "SELECT id, user_id, token_hash, created_at FROM sessions WHERE token_hash = $1 AND revoked_at IS NULL",
      [tokenHash],
    );
    const row = r.rows[0];
    return row ? { id: row.id, userId: row.user_id, tokenHash: row.token_hash, createdAt: row.created_at } : null;
  }

  async revokeAllForUser(userId: string): Promise<number> {
    const r = await this.pool.query(
      "UPDATE sessions SET revoked_at = now() WHERE user_id = $1 AND revoked_at IS NULL",
      [userId],
    );
    return r.rowCount ?? 0;
  }
}

function toUser(row: { id: string; email: string; password_hash: string }): User {
  return { id: row.id, email: row.email, passwordHash: row.password_hash };
}
