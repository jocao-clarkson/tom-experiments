import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../src/api/client.js";

const fast = { timeoutMs: 1000, maxAttempts: 3, backoffMs: 0 };

describe("ApiClient", () => {
  it("retries GET on 503", async () => {
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(new Response("busy", { status: 503 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const api = new ApiClient("https://api.test", "t", fast, fetchImpl as unknown as typeof fetch);
    await expect(api.get("/x")).resolves.toEqual({ ok: true });
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it("does not retry POST without an idempotency key", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response("busy", { status: 503 }));
    const api = new ApiClient("https://api.test", "t", fast, fetchImpl as unknown as typeof fetch);
    await expect(api.post("/x", { body: {} })).rejects.toThrow(/503/);
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
