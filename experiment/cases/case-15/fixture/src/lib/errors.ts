import type { NextFunction, Request, Response } from "express";

export class HttpError extends Error {
  constructor(readonly status: number, readonly code: string, message?: string) {
    super(message ?? code);
  }
}

export const notFound = (what = "resource") => new HttpError(404, "not_found", `${what} not found`);
export const badRequest = (message: string) => new HttpError(400, "bad_request", message);

export function errorHandler(err: unknown, _req: Request, res: Response, _next: NextFunction): void {
  if (err instanceof HttpError) {
    res.status(err.status).json({ error: { code: err.code, message: err.message } });
    return;
  }
  console.error(err);
  res.status(500).json({ error: { code: "internal", message: "internal error" } });
}
