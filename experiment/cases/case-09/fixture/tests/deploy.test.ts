import { PassThrough } from "node:stream";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { makeDeployCommand, type Deps } from "../src/commands/deploy.js";

function capture() {
  const s = new PassThrough();
  let buf = "";
  s.on("data", (c) => (buf += c));
  return { stream: s, text: () => buf };
}

function setup(confirmAnswer = true) {
  const out = capture();
  const err = capture();
  const deps: Deps = {
    api: {
      get: vi.fn(),
      post: vi.fn().mockResolvedValue({ id: "rel_9", service: "web", env: "production", version: "1.4.0" }),
    } as any,
    confirm: vi.fn().mockResolvedValue(confirmAnswer),
    stdout: out.stream,
    stderr: err.stream,
  };
  return { deps, out, err, cmd: makeDeployCommand(() => deps) };
}

describe("deploy", () => {
  beforeEach(() => {
    process.exitCode = undefined;
  });

  it("asks for confirmation in production and deploys", async () => {
    const { deps, out, cmd } = setup(true);
    await cmd.parseAsync(["web", "--version", "1.4.0", "--env", "production", "--json"], { from: "user" });
    expect(deps.confirm).toHaveBeenCalled();
    expect(JSON.parse(out.text())).toEqual({ releaseId: "rel_9", service: "web", env: "production", version: "1.4.0" });
    expect(process.exitCode).toBe(0);
  });

  it("aborts when confirmation is declined", async () => {
    const { deps, err, cmd } = setup(false);
    await cmd.parseAsync(["web", "--version", "1.4.0", "--env", "production"], { from: "user" });
    expect(deps.api.post).not.toHaveBeenCalled();
    expect(err.text()).toContain("Aborted.");
    expect(process.exitCode).toBe(1);
  });

  it("skips confirmation with --yes", async () => {
    const { deps, cmd } = setup(false);
    await cmd.parseAsync(["web", "--version", "1.4.0", "--env", "production", "--yes"], { from: "user" });
    expect(deps.confirm).not.toHaveBeenCalled();
    expect(deps.api.post).toHaveBeenCalled();
  });
});
