import type { OneTimeTokenRepo } from "../db/oneTimeTokenRepo.js";
import type { UserRepo } from "../db/userRepo.js";
import type { JobQueue } from "../jobs/queue.js";

export interface AuditSink {
  record(event: string, data: Record<string, string>): void;
}

export class EmailVerificationService {
  constructor(
    private readonly users: UserRepo,
    private readonly tokens: OneTimeTokenRepo,
    private readonly jobs: JobQueue,
    private readonly audit: AuditSink,
    private readonly baseUrl: string,
  ) {}

  async sendVerification(userId: string): Promise<void> {
    const user = await this.users.findById(userId);
    if (!user || user.emailVerified) return;
    await this.tokens.revokeAll(user.id, "email_verification");
    const token = await this.tokens.issue(user.id, "email_verification");
    const link = `${this.baseUrl}/verify-email?token=${encodeURIComponent(token)}`;
    await this.jobs.enqueue("send_mail", { template: "verify_email", to: user.email, vars: { link } });
    this.audit.record("email_verification_sent", { userId: user.id });
  }

  async confirm(token: string): Promise<boolean> {
    const consumed = await this.tokens.consume(token, "email_verification");
    if (!consumed) return false;
    await this.users.markEmailVerified(consumed.userId);
    this.audit.record("email_verified", { userId: consumed.userId });
    return true;
  }
}
