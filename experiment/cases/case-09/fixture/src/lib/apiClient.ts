import { debug } from "./log.js";

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly body: unknown) {
    super(`API request failed with status ${status}`);
  }
}

export interface RequestOptions {
  body?: unknown;
  timeoutMs?: number;
}

const RETRY_DELAYS_MS = [500, 1500, 4000];

/**
 * Deploy service client. GET requests are retried on network errors and 5xx
 * responses. Other methods are never retried: the deploy API's mutating
 * endpoints are not idempotent.
 */
export class ApiClient {
  constructor(private readonly baseUrl: string, private readonly token: string) {}

  async request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
    const attempts = method === "GET" ? RETRY_DELAYS_MS.length + 1 : 1;
    let lastErr: unknown;
    for (let i = 0; i < attempts; i++) {
      try {
        debug("api request", { method, path, attempt: i + 1, authorization: this.token });
        const res = await fetch(new URL(path, this.baseUrl), {
          method,
          headers: { authorization: `Bearer ${this.token}`, "content-type": "application/json" },
          body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
          signal: AbortSignal.timeout(opts.timeoutMs ?? 15_000),
        });
        const body = res.status === 204 ? undefined : await res.json().catch(() => undefined);
        if (res.ok) return body as T;
        lastErr = new ApiError(res.status, body);
        if (res.status < 500) throw lastErr;
      } catch (err) {
        if (err instanceof ApiError && err.status < 500) throw err;
        lastErr = err;
      }
      if (i < attempts - 1) await new Promise((r) => setTimeout(r, RETRY_DELAYS_MS[i]));
    }
    throw lastErr;
  }

  get<T>(path: string) {
    return this.request<T>("GET", path);
  }

  post<T>(path: string, body: unknown) {
    return this.request<T>("POST", path, { body });
  }
}
