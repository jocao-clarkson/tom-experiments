import { createHash, randomBytes, timingSafeEqual } from "node:crypto";

/** Opaque, URL-safe random token. Used for session ids and one-time links. */
export function generateToken(bytes = 32): string {
  return randomBytes(bytes).toString("base64url");
}

/** Tokens are persisted only as their SHA-256 hex digest. */
export function hashToken(token: string): string {
  return createHash("sha256").update(token, "utf8").digest("hex");
}

export function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}

export interface PolicyResult {
  ok: boolean;
  errors: string[];
}

export function validatePassword(pw: string): PolicyResult {
  const errors: string[] = [];
  if (pw.length < 12) errors.push("min_length");
  if (pw.length > 128) errors.push("max_length");
  if (!/[a-z]/.test(pw) || !/[A-Z]/.test(pw)) errors.push("mixed_case");
  if (!/[0-9]/.test(pw)) errors.push("digit");
  return { ok: errors.length === 0, errors };
}
