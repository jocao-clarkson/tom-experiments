import { createHash } from "crypto";
import type { NextFunction, Request, Response } from "express";
import type { Pool } from "pg";
import { UnauthorizedError } from "../lib/errors";

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Express {
    interface Request {
      tenantId: string;
    }
  }
}

export function requireApiKey(db: Pool) {
  return async (req: Request, _res: Response, next: NextFunction) => {
    try {
      const header = req.header("authorization") ?? "";
      const key = header.startsWith("Bearer ") ? header.slice(7) : "";
      if (!key) throw new UnauthorizedError();
      const hash = createHash("sha256").update(key).digest("hex");
      const r = await db.query("SELECT tenant_id FROM api_keys WHERE key_hash = $1 AND revoked_at IS NULL", [hash]);
      if (!r.rows[0]) throw new UnauthorizedError();
      req.tenantId = r.rows[0].tenant_id;
      next();
    } catch (err) {
      next(err);
    }
  };
}
