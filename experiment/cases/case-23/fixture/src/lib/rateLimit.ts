export interface LimitResult {
  allowed: boolean;
  retryAfterMs: number;
}

export interface Window {
  start: number;
  count: number;
}

/** Synchronous key/value store for window state. */
export interface WindowStore {
  get(key: string): Window | undefined;
  set(key: string, w: Window): void;
}

/**
 * Fixed-window counter keyed by an arbitrary string (IP, user id, ...).
 */
export class FixedWindowLimiter {
  constructor(
    private readonly limit: number,
    private readonly windowMs: number,
    private readonly store: WindowStore,
    private readonly now: () => number = Date.now,
  ) {}

  hit(key: string): LimitResult {
    const t = this.now();
    const w = this.store.get(key);
    if (!w || t - w.start >= this.windowMs) {
      this.store.set(key, { start: t, count: 1 });
      return { allowed: true, retryAfterMs: 0 };
    }
    w.count += 1;
    this.store.set(key, w);
    if (w.count > this.limit) {
      return { allowed: false, retryAfterMs: w.start + this.windowMs - t };
    }
    return { allowed: true, retryAfterMs: 0 };
  }
}
