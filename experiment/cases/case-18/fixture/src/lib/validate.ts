export interface IntParamOptions {
  min: number;
  max: number;
  default: number;
}

/**
 * Lenient integer parsing for query/body params: missing or non-numeric values
 * fall back to the default, and out-of-range values are clamped into [min, max].
 */
export function intParam(raw: unknown, opts: IntParamOptions): number {
  if (raw === undefined || raw === null || raw === "") return opts.default;
  const n = typeof raw === "number" ? raw : Number.parseInt(String(raw), 10);
  if (!Number.isFinite(n)) return opts.default;
  return Math.min(opts.max, Math.max(opts.min, Math.trunc(n)));
}

export function requiredString(raw: unknown, field: string, maxLen = 200): string {
  if (typeof raw !== "string" || raw.trim() === "" || raw.length > maxLen) {
    throw Object.assign(new Error(`${field} is required`), { status: 400 });
  }
  return raw.trim();
}
