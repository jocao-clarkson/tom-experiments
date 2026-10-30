import { ApiError } from "../errors.js";

const RETRYABLE = new Set([502, 503, 504]);

export interface RequestOptions {
  /** Defaults to true for GET and false for everything else. */
  retry?: boolean;
}

export class ApiClient {
  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
    private readonly fetchImpl: typeof fetch = fetch,
    private readonly timeoutMs = 15_000,
    private readonly sleep = (ms: number) => new Promise((r) => setTimeout(r, ms)),
  ) {}

  async request<T>(method: string, path: string, body?: unknown, opts: RequestOptions = {}): Promise<T> {
    const retry = opts.retry ?? method === "GET";
    const attempts = retry ? 4 : 1;
    let lastErr: unknown;
    for (let i = 0; i < attempts; i++) {
      if (i > 0) await this.sleep(250 * 2 ** (i - 1));
      let res: Response;
      try {
        res = await this.fetchImpl(this.baseUrl + path, {
          method,
          headers: { authorization: `Bearer ${this.token}`, "content-type": "application/json" },
          body: body === undefined ? undefined : JSON.stringify(body),
          signal: AbortSignal.timeout(this.timeoutMs),
        });
      } catch (err) {
        lastErr = err;
        continue;
      }
      if (RETRYABLE.has(res.status) && i < attempts - 1) {
        lastErr = new ApiError(res.status, "unavailable", `deploy service returned ${res.status}`);
        continue;
      }
      const data = res.status === 204 ? undefined : await res.json().catch(() => undefined);
      if (!res.ok) {
        const code = (data as { error?: string } | undefined)?.error ?? "error";
        throw new ApiError(res.status, code, `${method} ${path} failed: ${res.status} ${code}`);
      }
      return data as T;
    }
    throw lastErr instanceof ApiError ? lastErr : new ApiError(0, "network", `cannot reach deploy service: ${String(lastErr)}`);
  }
}
