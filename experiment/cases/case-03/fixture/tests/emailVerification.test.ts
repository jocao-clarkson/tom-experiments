import { describe, expect, it, vi } from "vitest";
import { EmailVerificationService } from "../src/services/emailVerification.js";

function setup(overrides: Partial<{ verified: boolean; consumeResult: any }> = {}) {
  const users = {
    findById: vi.fn().mockResolvedValue({ id: "u1", email: "a@example.com", emailVerified: overrides.verified ?? false }),
    markEmailVerified: vi.fn().mockResolvedValue(undefined),
  };
  const tokens = {
    issue: vi.fn().mockResolvedValue("tok123"),
    consume: vi.fn().mockResolvedValue(overrides.consumeResult ?? null),
    revokeAll: vi.fn().mockResolvedValue(undefined),
  };
  const jobs = { enqueue: vi.fn().mockResolvedValue(undefined) };
  const audit = { record: vi.fn() };
  const svc = new EmailVerificationService(users as any, tokens as any, jobs as any, audit, "https://app.example.com");
  return { svc, users, tokens, jobs, audit };
}

describe("EmailVerificationService", () => {
  it("revokes old tokens before issuing a new one", async () => {
    const { svc, tokens, jobs } = setup();
    await svc.sendVerification("u1");
    expect(tokens.revokeAll).toHaveBeenCalledWith("u1", "email_verification");
    expect(tokens.issue.mock.invocationCallOrder[0]).toBeGreaterThan(tokens.revokeAll.mock.invocationCallOrder[0]);
    expect(jobs.enqueue).toHaveBeenCalledWith("send_mail", {
      template: "verify_email",
      to: "a@example.com",
      vars: { link: "https://app.example.com/verify-email?token=tok123" },
    });
  });

  it("does nothing for already verified users", async () => {
    const { svc, jobs } = setup({ verified: true });
    await svc.sendVerification("u1");
    expect(jobs.enqueue).not.toHaveBeenCalled();
  });

  it("rejects unknown or used tokens", async () => {
    const { svc, users } = setup();
    expect(await svc.confirm("nope")).toBe(false);
    expect(users.markEmailVerified).not.toHaveBeenCalled();
  });

  it("marks the user verified for a valid token", async () => {
    const { svc, users, audit } = setup({ consumeResult: { userId: "u1", purpose: "email_verification" } });
    expect(await svc.confirm("tok123")).toBe(true);
    expect(users.markEmailVerified).toHaveBeenCalledWith("u1");
    expect(audit.record).toHaveBeenCalledWith("email_verified", { userId: "u1" });
  });
});
