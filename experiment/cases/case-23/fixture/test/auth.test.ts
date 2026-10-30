import bcrypt from "bcryptjs";
import { beforeEach, describe, expect, it } from "vitest";
import { AuthService } from "../src/services/authService.js";
import { FixedWindowLimiter } from "../src/lib/rateLimit.js";
import { FakeSessionRepo, FakeUserRepo } from "./fakes.js";

describe("AuthService.login", () => {
  let users: FakeUserRepo;
  let sessions: FakeSessionRepo;
  let svc: AuthService;

  beforeEach(async () => {
    users = new FakeUserRepo();
    sessions = new FakeSessionRepo();
    users.users.set("u1", { id: "u1", email: "ana@example.com", passwordHash: await bcrypt.hash("CorrectHorse9x", 4) });
    svc = new AuthService(users, sessions, () => new Date("2024-05-01T00:00:00Z"));
  });

  it("issues a session for valid credentials", async () => {
    const { sessionToken } = await svc.login("ANA@example.com", "CorrectHorse9x");
    expect(sessionToken).toHaveLength(43);
    expect(sessions.sessions[0].tokenHash).not.toBe(sessionToken);
  });

  it("rejects wrong password with the same error as unknown email", async () => {
    await expect(svc.login("ana@example.com", "nope")).rejects.toMatchObject({ code: "invalid_credentials" });
    await expect(svc.login("bob@example.com", "nope")).rejects.toMatchObject({ code: "invalid_credentials" });
  });
});

describe("FixedWindowLimiter", () => {
  it("blocks after the limit within a window", () => {
    let t = 0;
    const l = new FixedWindowLimiter(2, 1000, new Map(), () => t);
    expect(l.hit("k").allowed).toBe(true);
    expect(l.hit("k").allowed).toBe(true);
    expect(l.hit("k").allowed).toBe(false);
    t = 1000;
    expect(l.hit("k").allowed).toBe(true);
  });
});
