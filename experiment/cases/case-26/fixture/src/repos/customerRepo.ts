import type { Pool } from "pg";

export interface Customer {
  id: string;
  name: string;
  email: string;
}

export interface CustomerPage {
  rows: Customer[];
  last: { name: string; id: string } | null;
}

export async function listCustomers(
  db: Pool,
  tenantId: string,
  opts: { after: { name: string; id: string } | null; limit: number },
): Promise<CustomerPage> {
  const params: unknown[] = [tenantId, opts.limit + 1];
  let where = "tenant_id = $1";
  if (opts.after) {
    params.push(opts.after.name, opts.after.id);
    where += " AND (name, id) > ($3, $4)";
  }
  const r = await db.query(
    `SELECT id, name, email FROM customers WHERE ${where} ORDER BY name ASC, id ASC LIMIT $2`,
    params,
  );
  const rows = r.rows.slice(0, opts.limit);
  const hasMore = r.rows.length > opts.limit;
  const tail = rows[rows.length - 1];
  return { rows, last: hasMore && tail ? { name: tail.name, id: tail.id } : null };
}
