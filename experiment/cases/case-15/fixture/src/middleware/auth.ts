import type { NextFunction, Request, Response } from "express";
import jwt from "jsonwebtoken";
import { config } from "../config";
import { HttpError } from "../lib/errors";

declare module "express-serve-static-core" {
  interface Request {
    userId?: string;
  }
}

export function requireUser(req: Request, _res: Response, next: NextFunction): void {
  const header = req.header("authorization") ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  try {
    const claims = jwt.verify(token, config.auth.jwtPublicKey, { algorithms: ["RS256"] }) as { sub: string };
    req.userId = claims.sub;
    next();
  } catch {
    next(new HttpError(401, "unauthorized"));
  }
}
