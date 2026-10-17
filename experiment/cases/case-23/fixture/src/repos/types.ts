export interface User {
  id: string;
  email: string;
  passwordHash: string;
}

export interface UserRepo {
  findByEmail(email: string): Promise<User | null>;
  findById(id: string): Promise<User | null>;
  updatePasswordHash(userId: string, hash: string): Promise<void>;
}

export interface Session {
  id: string;
  userId: string;
  tokenHash: string;
  createdAt: Date;
}

export interface SessionRepo {
  create(userId: string, tokenHash: string): Promise<Session>;
  findByTokenHash(tokenHash: string): Promise<Session | null>;
  revokeAllForUser(userId: string): Promise<number>;
}

export interface Mailer {
  /** Puts a templated email on the outbound queue. Never blocks on SMTP. */
  enqueue(template: string, to: string, vars: Record<string, string>): Promise<void>;
}
