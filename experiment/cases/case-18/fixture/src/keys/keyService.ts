import { constantTimeEqual, hashSecret, randomSecret } from "../lib/crypto";
import { logger } from "../lib/logger";
import type { ApiKey, KeyRepo } from "./keyRepo";

export interface Actor {
  id: string;
  orgId: string;
  role: "member" | "org_admin";
}

export class ForbiddenError extends Error {
  readonly status = 403;
}

export class KeyService {
  constructor(private readonly repo: KeyRepo) {}

  /** Owners manage their own keys; org admins manage any key in their org. */
  assertCanManage(actor: Actor, key: ApiKey): void {
    const sameOrg = key.orgId === actor.orgId;
    if (!sameOrg || (key.ownerId !== actor.id && actor.role !== "org_admin")) {
      throw new ForbiddenError("not allowed to manage this key");
    }
  }

  async create(actor: Actor, name: string, ttlDays: number | null) {
    const plaintext = randomSecret();
    const key = await this.repo.insert({
      orgId: actor.orgId,
      ownerId: actor.id,
      name,
      prefix: plaintext.slice(0, 11),
      secretHash: hashSecret(plaintext),
      expiresAt: ttlDays ? new Date(Date.now() + ttlDays * 86_400_000) : null,
    });
    logger.audit("api_key.created", { keyId: key.id, orgId: key.orgId, actorId: actor.id });
    return { key, plaintext };
  }

  async verify(presented: string): Promise<ApiKey | null> {
    const candidates = await this.repo.byPrefix(presented.slice(0, 11));
    const hash = hashSecret(presented);
    const now = Date.now();
    return (
      candidates.find(
        (k) => k.status === "active" && (!k.expiresAt || k.expiresAt.getTime() > now) && constantTimeEqual(k.secretHash, hash),
      ) ?? null
    );
  }
}
