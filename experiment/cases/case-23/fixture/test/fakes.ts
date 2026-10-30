import type { Mailer, Session, SessionRepo, User, UserRepo } from "../src/repos/types.js";

export class FakeUserRepo implements UserRepo {
  users = new Map<string, User>();
  async findByEmail(email: string) {
    return [...this.users.values()].find((u) => u.email.toLowerCase() === email.toLowerCase()) ?? null;
  }
  async findById(id: string) {
    return this.users.get(id) ?? null;
  }
  async updatePasswordHash(userId: string, hash: string) {
    const u = this.users.get(userId);
    if (u) u.passwordHash = hash;
  }
}

export class FakeSessionRepo implements SessionRepo {
  sessions: (Session & { revoked: boolean })[] = [];
  async create(userId: string, tokenHash: string) {
    const s = { id: String(this.sessions.length + 1), userId, tokenHash, createdAt: new Date(), revoked: false };
    this.sessions.push(s);
    return s;
  }
  async findByTokenHash(tokenHash: string) {
    return this.sessions.find((s) => s.tokenHash === tokenHash && !s.revoked) ?? null;
  }
  async revokeAllForUser(userId: string) {
    let n = 0;
    for (const s of this.sessions) if (s.userId === userId && !s.revoked) { s.revoked = true; n++; }
    return n;
  }
}

export class FakeMailer implements Mailer {
  sent: { template: string; to: string; vars: Record<string, string> }[] = [];
  async enqueue(template: string, to: string, vars: Record<string, string>) {
    this.sent.push({ template, to, vars });
  }
}
