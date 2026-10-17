import type { Pool } from "pg";

export interface User {
  id: string;
  email: string;
  emailVerified: boolean;
  passwordHash: string;
}

export class UserRepo {
  constructor(private readonly db: Pool) {}

  async findByEmail(email: string): Promise<User | null> {
    const res = await this.db.query(
      `SELECT id, email, email_verified, password_hash FROM users WHERE lower(email) = lower($1)`,
      [email],
    );
    return res.rowCount ? toUser(res.rows[0]) : null;
  }

  async findById(id: string): Promise<User | null> {
    const res = await this.db.query(
      `SELECT id, email, email_verified, password_hash FROM users WHERE id = $1`,
      [id],
    );
    return res.rowCount ? toUser(res.rows[0]) : null;
  }

  async markEmailVerified(id: string): Promise<void> {
    await this.db.query(`UPDATE users SET email_verified = true WHERE id = $1`, [id]);
  }

  async updatePasswordHash(id: string, passwordHash: string): Promise<void> {
    await this.db.query(`UPDATE users SET password_hash = $2, updated_at = now() WHERE id = $1`, [
      id,
      passwordHash,
    ]);
  }

  /** Deletes all refresh sessions for the user, signing them out everywhere. */
  async revokeSessions(id: string): Promise<number> {
    const res = await this.db.query(`DELETE FROM sessions WHERE user_id = $1`, [id]);
    return res.rowCount ?? 0;
  }
}

function toUser(row: any): User {
  return {
    id: row.id,
    email: row.email,
    emailVerified: row.email_verified,
    passwordHash: row.password_hash,
  };
}
