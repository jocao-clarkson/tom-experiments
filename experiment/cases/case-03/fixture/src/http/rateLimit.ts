import type { NextFunction, Request, Response } from "express";

interface Window {
  count: number;
  resetAt: number;
}

export interface RateLimitOptions {
  limit: number;
  windowMs: number;
  key: (req: Request) => string | undefined;
  now?: () => number;
}

/** Fixed-window limiter. Returns 429 with Retry-After when the limit is hit. */
export function rateLimit(opts: RateLimitOptions) {
  const windows = new Map<string, Window>();
  const now = opts.now ?? Date.now;

  return function rateLimitMiddleware(req: Request, res: Response, next: NextFunction) {
    const key = opts.key(req);
    if (!key) return next();

    const t = now();
    let w = windows.get(key);
    if (!w || w.resetAt <= t) {
      w = { count: 0, resetAt: t + opts.windowMs };
      windows.set(key, w);
    }
    w.count += 1;
    if (w.count > opts.limit) {
      res.setHeader("Retry-After", Math.ceil((w.resetAt - t) / 1000));
      return res.status(429).json({ error: { code: "rate_limited", message: "Too many requests" } });
    }
    next();
  };
}
