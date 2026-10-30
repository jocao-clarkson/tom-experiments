import { Pool, type QueryResultRow } from "pg";
import { config } from "../config";

export const pool = new Pool({
  connectionString: config.db.url,
  max: config.db.poolSize,
  statement_timeout: config.db.statementTimeoutMs,
});

export async function query<T extends QueryResultRow>(text: string, params: unknown[] = []) {
  return pool.query<T>(text, params);
}

/** Runs one statement on behalf of a user; row-level security policies read `app.user_id`. */
export async function userQuery<T extends QueryResultRow>(userId: string, text: string, params: unknown[] = []) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    await client.query("SELECT set_config('app.user_id', $1, true)", [userId]);
    const result = await client.query<T>(text, params);
    await client.query("COMMIT");
    return result;
  } catch (err) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw err;
  } finally {
    client.release();
  }
}
