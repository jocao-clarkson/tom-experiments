import { hashSecret } from "../lib/crypto";
import type { ApiKey } from "./keyRepo";

export interface VerifyCacheOptions {
  ttlMs: number;
  maxEntries: number;
}

const DEFAULTS: VerifyCacheOptions = { ttlMs: 5 * 60_000, maxEntries: 10_000 };

type Verifier = (presented: string) => Promise<ApiKey | null>;

/** Keeps successful verifications in memory so the gateway's hot path skips the database. */
export class VerifyCache {
  private readonly entries = new Map<string, { key: ApiKey; until: number }>();
  private readonly opts: VerifyCacheOptions;

  constructor(private readonly verifier: Verifier, opts: Partial<VerifyCacheOptions> = {}) {
    this.opts = { ...DEFAULTS, ...opts };
  }

  async verify(presented: string): Promise<ApiKey | null> {
    const h = hashSecret(presented);
    const hit = this.entries.get(h);
    if (hit && hit.until > Date.now()) return hit.key;

    const key = await this.verifier(presented);
    if (!key) {
      this.entries.delete(h);
      return null;
    }
    if (this.entries.size >= this.opts.maxEntries) this.entries.clear();
    this.entries.set(h, { key, until: Date.now() + this.opts.ttlMs });
    return key;
  }

  evict(keyId: string): void {
    for (const [h, e] of this.entries) {
      if (e.key.id === keyId) this.entries.delete(h);
    }
  }
}
