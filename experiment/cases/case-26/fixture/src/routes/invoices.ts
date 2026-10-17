import { Router } from "express";
import type { AppDeps } from "../app";
import { ValidationError } from "../lib/errors";
import { parseLimit } from "../lib/pagination";
import { listInvoices, type InvoiceStatus } from "../repos/invoiceRepo";

const STATUSES: InvoiceStatus[] = ["draft", "open", "paid", "void"];

export function invoicesRouter(deps: AppDeps): Router {
  const r = Router();

  r.get("/invoices", async (req, res, next) => {
    try {
      const limit = parseLimit(req.query.limit, { def: 25, max: 100 });
      const offset = req.query.offset === undefined ? 0 : Number(req.query.offset);
      if (!Number.isInteger(offset) || offset < 0) throw new ValidationError("invalid_offset");
      const status = req.query.status as InvoiceStatus | undefined;
      if (status && !STATUSES.includes(status)) throw new ValidationError("invalid_status");
      const rows = await listInvoices(deps.db, req.tenantId, { offset, limit, status });
      res.json({ data: rows });
    } catch (err) {
      next(err);
    }
  });

  return r;
}
