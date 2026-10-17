import type { NextFunction, Request, Response } from "express";

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, message?: string) {
    super(message ?? code);
  }
}

export class ValidationError extends ApiError {
  constructor(code: string, message?: string) {
    super(400, code, message);
  }
}

export class UnauthorizedError extends ApiError {
  constructor() {
    super(401, "unauthorized", "missing or invalid API key");
  }
}

export class NotFoundError extends ApiError {
  constructor(what: string) {
    super(404, "not_found", `${what} not found`);
  }
}

export function errorMiddleware(err: unknown, _req: Request, res: Response, _next: NextFunction) {
  if (err instanceof ApiError) {
    res.status(err.status).json({ error: { code: err.code, message: err.message } });
    return;
  }
  console.error(err);
  res.status(500).json({ error: { code: "internal_error", message: "internal error" } });
}
