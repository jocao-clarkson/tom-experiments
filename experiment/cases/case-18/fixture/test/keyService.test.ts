import { KeyService, ForbiddenError, type Actor } from "../src/keys/keyService";
import type { ApiKey, KeyRepo } from "../src/keys/keyRepo";
import { hashSecret } from "../src/lib/crypto";

const key = (over: Partial<ApiKey> = {}): ApiKey => ({
  id: "k1", orgId: "o1", ownerId: "u1", name: "ci", prefix: "rk_abcdefgh", secretHash: "",
  status: "active", createdAt: new Date(), expiresAt: null, ...over,
});

describe("KeyService", () => {
  const service = new KeyService({} as KeyRepo);
  const member: Actor = { id: "u2", orgId: "o1", role: "member" };
  const admin: Actor = { id: "u3", orgId: "o1", role: "org_admin" };
  const otherAdmin: Actor = { id: "u4", orgId: "o2", role: "org_admin" };

  it("lets owners and same-org admins manage keys", () => {
    expect(() => service.assertCanManage({ ...member, id: "u1" }, key())).not.toThrow();
    expect(() => service.assertCanManage(admin, key())).not.toThrow();
  });

  it("rejects other members and admins of other orgs", () => {
    expect(() => service.assertCanManage(member, key())).toThrow(ForbiddenError);
    expect(() => service.assertCanManage(otherAdmin, key())).toThrow(ForbiddenError);
  });

  it("verifies only active, unexpired keys", async () => {
    const secret = "rk_abcdefgh-secret";
    const repo = { byPrefix: async () => [key({ secretHash: hashSecret(secret), expiresAt: new Date(Date.now() - 1000) })] };
    expect(await new KeyService(repo as unknown as KeyRepo).verify(secret)).toBeNull();
  });
});
