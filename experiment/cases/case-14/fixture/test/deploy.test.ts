import { describe, expect, it, vi } from "vitest";
import { PassThrough } from "node:stream";
import { deployCommand } from "../src/commands/deploy.js";
import { UsageError } from "../src/errors.js";
import type { ApiClient } from "../src/api/client.js";

function ctx(isTTY = false) {
  const stdout = new PassThrough();
  const stdin = Object.assign(new PassThrough(), { isTTY });
  let written = "";
  stdout.on("data", (c) => (written += c));
  return { out: { json: false, stdout, stdin }, written: () => written };
}

describe("deploy", () => {
  it("posts with an idempotency key when --yes is given", async () => {
    const post = vi.fn().mockResolvedValue({ id: "r-9", status: "pending" });
    const { out } = ctx();
    const code = await deployCommand({ post } as unknown as ApiClient, out, ["web"], { version: "2.1.0", yes: true });
    expect(code).toBe(0);
    expect(post.mock.calls[0][1].idempotencyKey).toMatch(/[0-9a-f-]{36}/);
  });

  it("refuses to prompt without a terminal", async () => {
    const { out } = ctx(false);
    await expect(
      deployCommand({ post: vi.fn() } as unknown as ApiClient, out, ["web"], { version: "2.1.0", yes: false }),
    ).rejects.toBeInstanceOf(UsageError);
  });
});
