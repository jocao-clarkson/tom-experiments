export interface LimitResult {
  allowed: boolean;
  retryAfterMs: number;
}

/**
 * Fixed-window counter keyed by an arbitrary string (IP, user id, ...).
 */
export class FixedWindowLimiter {
  private windows = new Map<string, { start: number; count: number }>();

  constructor(
    private readonly limit: number,
    private readonly windowMs: number,
    private readonly now: () => number = Date.now,
  ) {}

  hit(key: string): LimitResult {
    const t = this.now();
    const w = this.windows.get(key);
    if (!w || t - w.start >= this.windowMs) {
      this.windows.set(key, { start: t, count: 1 });
      return { allowed: true, retryAfterMs: 0 };
    }
    w.count += 1;
    if (w.count > this.limit) {
      return { allowed: false, retryAfterMs: w.start + this.windowMs - t };
    }
    return { allowed: true, retryAfterMs: 0 };
  }
}
