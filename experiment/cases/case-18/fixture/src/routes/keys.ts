import { Router, type Request } from "express";
import { intParam, requiredString } from "../lib/validate";
import type { Actor, KeyService } from "../keys/keyService";
import type { KeyRepo } from "../keys/keyRepo";
import type { VerifyCache } from "../keys/verifyCache";

const actorOf = (req: Request) => (req as Request & { actor: Actor }).actor;

export function keysRouter(service: KeyService, repo: KeyRepo, cache: VerifyCache): Router {
  const r = Router();

  r.post("/", async (req, res, next) => {
    try {
      const name = requiredString(req.body.name, "name");
      const ttlDays = req.body.ttl_days === undefined ? null : intParam(req.body.ttl_days, { min: 1, max: 365, default: 90 });
      const { key, plaintext } = await service.create(actorOf(req), name, ttlDays);
      res.status(201).json({ id: key.id, prefix: key.prefix, secret: plaintext, expiresAt: key.expiresAt });
    } catch (err) {
      next(err);
    }
  });

  r.delete("/:id", async (req, res, next) => {
    try {
      const key = await repo.byId(req.params.id);
      if (!key) return res.status(404).json({ error: "not_found" });
      service.assertCanManage(actorOf(req), key);
      await repo.setStatus(key.id, "revoked");
      cache.evict(key.id);
      res.status(204).end();
    } catch (err) {
      next(err);
    }
  });

  return r;
}
