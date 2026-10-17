import { badRequest } from "./errors";

/** Keyset pagination shared by every list endpoint the app consumes. */
export const DEFAULT_LIMIT = 20;
export const MAX_LIMIT = 100;

export interface Cursor {
  createdAt: string;
  id: string;
}

export function parseLimit(raw: unknown): number {
  if (raw === undefined) return DEFAULT_LIMIT;
  const n = Number(raw);
  if (!Number.isInteger(n) || n < 1) throw badRequest("limit must be a positive integer");
  return Math.min(n, MAX_LIMIT);
}

export function encodeCursor(c: Cursor): string {
  return Buffer.from(JSON.stringify(c)).toString("base64url");
}

export function decodeCursor(raw: unknown): Cursor | null {
  if (raw === undefined || raw === "") return null;
  try {
    const c = JSON.parse(Buffer.from(String(raw), "base64url").toString("utf8"));
    if (typeof c.createdAt === "string" && typeof c.id === "string") return c;
  } catch {
    // fall through
  }
  throw badRequest("invalid cursor");
}

/**
 * Callers fetch `limit + 1` rows ordered by (created_at DESC, id DESC) after the cursor.
 * The extra row tells us whether another page exists.
 */
export function toPage<T extends { id: string; created_at: Date }>(rows: T[], limit: number) {
  const items = rows.slice(0, limit);
  const last = items[items.length - 1];
  const nextCursor =
    rows.length > limit && last ? encodeCursor({ createdAt: last.created_at.toISOString(), id: last.id }) : null;
  return { items, nextCursor };
}
