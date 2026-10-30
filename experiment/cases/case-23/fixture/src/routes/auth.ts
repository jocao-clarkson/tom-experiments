import { Router } from "express";
import type { FixedWindowLimiter } from "../lib/rateLimit.js";
import { AuthError, type AuthService } from "../services/authService.js";

export function authRouter(auth: AuthService, loginLimiter: FixedWindowLimiter): Router {
  const r = Router();

  r.post("/auth/login", async (req, res, next) => {
    const limit = loginLimiter.hit(`login:${req.ip}`);
    if (!limit.allowed) {
      res.setHeader("Retry-After", Math.ceil(limit.retryAfterMs / 1000));
      return res.status(429).json({ error: "rate_limited" });
    }
    try {
      const { email, password } = req.body ?? {};
      res.json(await auth.login(String(email ?? ""), String(password ?? "")));
    } catch (err) {
      if (err instanceof AuthError) return res.status(err.status).json({ error: err.code });
      next(err);
    }
  });

  return r;
}
