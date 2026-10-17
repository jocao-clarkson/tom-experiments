import PgBoss from "pg-boss";

export interface EnqueueOptions {
  /** Total attempts including the first. Defaults to 3. */
  attempts?: number;
  backoffSeconds?: number;
  /** Jobs with the same singletonKey are not enqueued twice while one is pending. */
  singletonKey?: string;
}

export type Handler<T> = (payload: T) => Promise<void>;

/**
 * Background jobs backed by pg-boss. A handler that throws is retried as a
 * whole, with exponential backoff, until attempts are used up.
 */
export class JobQueue {
  constructor(private readonly boss: PgBoss) {}

  async enqueue<T extends object>(name: string, payload: T, opts: EnqueueOptions = {}): Promise<void> {
    const attempts = opts.attempts ?? 3;
    await this.boss.send(name, payload, {
      retryLimit: attempts - 1,
      retryDelay: opts.backoffSeconds ?? 10,
      retryBackoff: true,
      singletonKey: opts.singletonKey,
    });
  }

  async register<T extends object>(name: string, handler: Handler<T>): Promise<void> {
    await this.boss.work<T>(name, async ([job]) => {
      await handler(job.data);
    });
  }
}
