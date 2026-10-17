import { Router } from "express";
import type { AppDeps } from "../app";
import { decodeCursor, encodeCursor, parseLimit } from "../lib/pagination";
import { listCustomers } from "../repos/customerRepo";

export function customersRouter(deps: AppDeps): Router {
  const r = Router();

  r.get("/customers", async (req, res, next) => {
    try {
      const limit = parseLimit(req.query.limit, { def: 50, max: 200 });
      const raw = typeof req.query.cursor === "string" ? req.query.cursor : undefined;
      const after = raw ? decodeCursor<{ name: string; id: string; t: string }>(raw, deps.cursorSecret) : null;
      const scoped = after && after.t === req.tenantId ? after : null;
      const page = await listCustomers(deps.db, req.tenantId, { after: scoped, limit });
      res.json({
        data: page.rows,
        next_cursor: page.last ? encodeCursor({ ...page.last, t: req.tenantId }, deps.cursorSecret) : null,
      });
    } catch (err) {
      next(err);
    }
  });

  return r;
}
