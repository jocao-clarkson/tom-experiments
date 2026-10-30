import assert from "node:assert/strict";
import { PassThrough } from "node:stream";
import { test } from "node:test";
import { ApiClient } from "../src/api/client.js";
import { deploy } from "../src/commands/deploy.js";
import { AbortError } from "../src/errors.js";
import { Output } from "../src/ui/output.js";

function fakeFetch(responses: Array<{ status: number; body?: unknown }>) {
  const calls: Array<{ url: string; method: string }> = [];
  const impl = (async (url: string, init: RequestInit) => {
    calls.push({ url, method: init.method ?? "GET" });
    const r = responses.shift() ?? { status: 500 };
    return new Response(r.body === undefined ? null : JSON.stringify(r.body), { status: r.status });
  }) as unknown as typeof fetch;
  return { impl, calls };
}

function capture() {
  const stdout = new PassThrough();
  let text = "";
  stdout.on("data", (c) => (text += c));
  return { stdout, text: () => text };
}

test("deploy --wait reports final state as one JSON document", async () => {
  const f = fakeFetch([
    { status: 201, body: { id: "d1", state: "pending" } },
    { status: 200, body: { id: "d1", state: "running" } },
    { status: 200, body: { id: "d1", state: "succeeded" } },
  ]);
  const api = new ApiClient("https://x", "t", f.impl, 1000, async () => {});
  const cap = capture();
  const out = new Output({ json: true, isTTY: false, stdout: cap.stdout });
  const code = await deploy(api, out, { service: "web", release: "r9", yes: true, wait: true, isTTY: false }, async () => {});
  assert.equal(code, 0);
  assert.deepEqual(JSON.parse(cap.text()), { id: "d1", state: "succeeded" });
});

test("deploy refuses to run non-interactively without --yes", async () => {
  const f = fakeFetch([]);
  const api = new ApiClient("https://x", "t", f.impl);
  const out = new Output({ json: false, isTTY: false, stdout: new PassThrough() });
  await assert.rejects(deploy(api, out, { service: "web", release: "r9", yes: false, wait: false, isTTY: false }), AbortError);
  assert.equal(f.calls.length, 0);
});

test("POST is not retried on 503", async () => {
  const f = fakeFetch([{ status: 503 }]);
  const api = new ApiClient("https://x", "t", f.impl, 1000, async () => {});
  await assert.rejects(api.request("POST", "/services/web/deploys", {}));
  assert.equal(f.calls.length, 1);
});
