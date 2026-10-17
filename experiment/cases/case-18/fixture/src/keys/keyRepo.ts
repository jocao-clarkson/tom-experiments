import { Pool } from "pg";

export type KeyStatus = "active" | "revoked" | "expired";

export interface ApiKey {
  id: string;
  orgId: string;
  ownerId: string;
  name: string;
  prefix: string;
  secretHash: string;
  status: KeyStatus;
  createdAt: Date;
  expiresAt: Date | null;
}

const COLS = `id, org_id AS "orgId", owner_id AS "ownerId", name, prefix, secret_hash AS "secretHash",
  status, created_at AS "createdAt", expires_at AS "expiresAt"`;

export class KeyRepo {
  constructor(private readonly db: Pool) {}

  async insert(k: Omit<ApiKey, "id" | "createdAt" | "status">): Promise<ApiKey> {
    const { rows } = await this.db.query<ApiKey>(
      `INSERT INTO api_keys (org_id, owner_id, name, prefix, secret_hash, status, expires_at)
       VALUES ($1, $2, $3, $4, $5, 'active', $6) RETURNING ${COLS}`,
      [k.orgId, k.ownerId, k.name, k.prefix, k.secretHash, k.expiresAt],
    );
    return rows[0];
  }

  async byId(id: string): Promise<ApiKey | null> {
    const { rows } = await this.db.query<ApiKey>(`SELECT ${COLS} FROM api_keys WHERE id = $1`, [id]);
    return rows[0] ?? null;
  }

  async byPrefix(prefix: string): Promise<ApiKey[]> {
    const { rows } = await this.db.query<ApiKey>(`SELECT ${COLS} FROM api_keys WHERE prefix = $1`, [prefix]);
    return rows;
  }

  async listForOrg(orgId: string): Promise<ApiKey[]> {
    const { rows } = await this.db.query<ApiKey>(`SELECT ${COLS} FROM api_keys WHERE org_id = $1 ORDER BY created_at DESC`, [orgId]);
    return rows;
  }

  async setStatus(id: string, status: KeyStatus): Promise<void> {
    await this.db.query(`UPDATE api_keys SET status = $2 WHERE id = $1`, [id, status]);
  }

  async expireDue(): Promise<number> {
    const { rowCount } = await this.db.query(
      `UPDATE api_keys SET status = 'expired' WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at < now()`,
    );
    return rowCount ?? 0;
  }
}
