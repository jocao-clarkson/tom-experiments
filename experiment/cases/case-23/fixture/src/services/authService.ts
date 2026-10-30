import bcrypt from "bcryptjs";
import { generateToken, hashToken } from "../lib/credentials.js";
import { logger } from "../lib/logger.js";
import type { SessionRepo, UserRepo } from "../repos/types.js";

export class AuthError extends Error {
  constructor(public readonly code: string, public readonly status = 400) {
    super(code);
  }
}

export class AuthService {
  constructor(
    private readonly users: UserRepo,
    private readonly sessions: SessionRepo,
    private readonly now: () => Date = () => new Date(),
  ) {}

  async login(email: string, password: string): Promise<{ sessionToken: string }> {
    const user = await this.users.findByEmail(email);
    const ok = user ? await bcrypt.compare(password, user.passwordHash) : false;
    if (!user || !ok) {
      throw new AuthError("invalid_credentials", 401);
    }
    const token = generateToken();
    await this.sessions.create(user.id, hashToken(token));
    logger.info("login", { userId: user.id, at: this.now().toISOString() });
    return { sessionToken: token };
  }
}
