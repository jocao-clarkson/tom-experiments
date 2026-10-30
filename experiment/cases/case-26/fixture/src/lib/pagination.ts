import { createHmac, timingSafeEqual } from "crypto";
import { ValidationError } from "./errors";

/**
 * Opaque, signed cursors. The payload is JSON; the signature stops clients
 * from crafting cursors that point at arbitrary rows.
 */
export function encodeCursor(payload: Record<string, unknown>, secret: string): string {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  return `${body}.${sign(body, secret)}`;
}

/** Returns the payload, or null when the cursor is malformed or unsigned. */
export function decodeCursor<T = Record<string, unknown>>(cursor: string, secret: string): T | null {
  const [body, sig] = cursor.split(".");
  if (!body || !sig) return null;
  const expected = Buffer.from(sign(body, secret));
  const given = Buffer.from(sig);
  if (expected.length !== given.length || !timingSafeEqual(expected, given)) return null;
  try {
    return JSON.parse(Buffer.from(body, "base64url").toString("utf8")) as T;
  } catch {
    return null;
  }
}

export function parseLimit(raw: unknown, opts: { def: number; max: number }): number {
  if (raw === undefined) return opts.def;
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 1 || n > opts.max) {
    throw new ValidationError("invalid_limit", `limit must be an integer from 1 to ${opts.max}`);
  }
  return n;
}

function sign(body: string, secret: string): string {
  return createHmac("sha256", secret).update(body).digest("base64url");
}
