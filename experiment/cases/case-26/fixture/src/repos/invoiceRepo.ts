import type { Pool } from "pg";

export type InvoiceStatus = "draft" | "open" | "paid" | "void";

export interface Invoice {
  id: string;
  customer_id: string;
  number: string;
  status: InvoiceStatus;
  total_cents: number;
  currency: string;
  created_at: string;
}

export async function listInvoices(
  db: Pool,
  tenantId: string,
  opts: { offset: number; limit: number; status?: InvoiceStatus },
): Promise<Invoice[]> {
  const params: unknown[] = [tenantId, opts.limit, opts.offset];
  let where = "tenant_id = $1";
  if (opts.status) {
    params.push(opts.status);
    where += ` AND status = $${params.length}`;
  }
  const r = await db.query(
    `SELECT id, customer_id, number, status, total_cents, currency, created_at
     FROM invoices WHERE ${where}
     ORDER BY created_at DESC LIMIT $2 OFFSET $3`,
    params,
  );
  return r.rows;
}
