import { ApiError } from "../errors.js";

export interface RequestOptions {
  body?: unknown;
  /** POSTs are only retried when an idempotency key is supplied. */
  idempotencyKey?: string;
}

const RETRYABLE = new Set([429, 502, 503, 504]);

export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
    private readonly opts = { timeoutMs: 10_000, maxAttempts: 3, backoffMs: 300 },
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  get<T>(path: string): Promise<T> {
    return this.send<T>("GET", path, {}, true);
  }

  post<T>(path: string, options: RequestOptions = {}): Promise<T> {
    return this.send<T>("POST", path, options, options.idempotencyKey !== undefined);
  }

  private async send<T>(method: string, path: string, options: RequestOptions, retryable: boolean): Promise<T> {
    const attempts = retryable ? this.opts.maxAttempts : 1;
    let lastError: unknown;
    for (let attempt = 1; attempt <= attempts; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.opts.timeoutMs);
      try {
        const headers: Record<string, string> = {
          authorization: `Bearer ${this.token}`,
          "content-type": "application/json",
        };
        if (options.idempotencyKey) headers["idempotency-key"] = options.idempotencyKey;
        const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
          method,
          headers,
          body: options.body === undefined ? undefined : JSON.stringify(options.body),
          signal: controller.signal,
        });
        if (res.ok) return (await res.json()) as T;
        const text = await res.text();
        lastError = new ApiError(`${method} ${path} failed with ${res.status}: ${text.slice(0, 200)}`, res.status);
        if (!RETRYABLE.has(res.status)) throw lastError;
      } catch (err) {
        if (err instanceof ApiError && !RETRYABLE.has(err.status ?? 0)) throw err;
        lastError = err instanceof ApiError ? err : new ApiError(`${method} ${path}: ${(err as Error).message}`);
      } finally {
        clearTimeout(timer);
      }
      if (attempt < attempts) await new Promise((r) => setTimeout(r, this.opts.backoffMs * 2 ** (attempt - 1)));
    }
    throw lastError;
  }
}
