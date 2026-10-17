import { Router } from "express";
import type { EmailVerificationService } from "../services/emailVerification.js";
import { rateLimit } from "./rateLimit.js";

export interface Services {
  emailVerification: EmailVerificationService;
}

export function authRoutes(services: Services): Router {
  const r = Router();

  r.post(
    "/auth/verify-email/resend",
    rateLimit({ limit: 3, windowMs: 60 * 60 * 1000, key: (req) => req.user?.id }),
    async (req, res, next) => {
      try {
        if (!req.user) return res.status(401).json({ error: { code: "unauthenticated", message: "Sign in required" } });
        await services.emailVerification.sendVerification(req.user.id);
        res.status(202).end();
      } catch (err) {
        next(err);
      }
    },
  );

  r.post("/auth/verify-email/confirm", async (req, res, next) => {
    try {
      const token = typeof req.body?.token === "string" ? req.body.token : "";
      const ok = await services.emailVerification.confirm(token);
      if (!ok) return res.status(400).json({ error: { code: "invalid_token", message: "Link is invalid or expired" } });
      res.status(204).end();
    } catch (err) {
      next(err);
    }
  });

  return r;
}
