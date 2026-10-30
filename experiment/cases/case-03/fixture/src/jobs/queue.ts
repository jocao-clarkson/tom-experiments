import type { Pool } from "pg";

export type JobKind = "send_mail";

export interface Job {
  id: string;
  kind: JobKind;
  payload: Record<string, unknown>;
  attempts: number;
}

export type JobHandler = (job: Job) => Promise<void>;

const MAX_ATTEMPTS = 5;
const LOCK_TIMEOUT = "5 minutes";

/** Postgres-backed job queue. Any instance can enqueue; every instance runs a worker. */
export class JobQueue {
  constructor(private readonly db: Pool) {}

  async enqueue(kind: JobKind, payload: Record<string, unknown>): Promise<void> {
    await this.db.query(`INSERT INTO jobs (kind, payload) VALUES ($1, $2)`, [kind, JSON.stringify(payload)]);
  }

  /** Claims the next due job. Rows locked by another worker are skipped. */
  async claim(): Promise<Job | null> {
    const res = await this.db.query(
      `UPDATE jobs SET locked_at = now(), attempts = attempts + 1
        WHERE id = (
          SELECT id FROM jobs
           WHERE done_at IS NULL AND run_at <= now() AND attempts < $1
             AND (locked_at IS NULL OR locked_at < now() - $2::interval)
           ORDER BY run_at
           FOR UPDATE SKIP LOCKED
           LIMIT 1)
        RETURNING id, kind, payload, attempts`,
      [MAX_ATTEMPTS, LOCK_TIMEOUT],
    );
    if (res.rowCount === 0) return null;
    const row = res.rows[0];
    return { id: String(row.id), kind: row.kind, payload: row.payload, attempts: row.attempts };
  }

  async complete(id: string): Promise<void> {
    await this.db.query(`UPDATE jobs SET done_at = now(), locked_at = NULL WHERE id = $1`, [id]);
  }

  async retryLater(id: string, attempts: number, error: string): Promise<void> {
    const delaySeconds = Math.min(2 ** attempts * 30, 3600);
    await this.db.query(
      `UPDATE jobs SET locked_at = NULL, run_at = now() + make_interval(secs => $2), last_error = $3
        WHERE id = $1`,
      [id, delaySeconds, error],
    );
  }
}

export interface WorkerOptions {
  pollMs: number;
  onError: (job: Job, err: unknown) => void;
  onPollError: (err: unknown) => void;
}

/** Polls the queue and runs handlers one job at a time. Returns a stop function. */
export function startWorker(
  queue: JobQueue,
  handlers: Record<JobKind, JobHandler>,
  opts: WorkerOptions,
): () => void {
  let stopped = false;
  let timer: NodeJS.Timeout | undefined;

  async function tick(): Promise<void> {
    try {
      for (let job = await queue.claim(); job && !stopped; job = await queue.claim()) {
        try {
          await handlers[job.kind](job);
          await queue.complete(job.id);
        } catch (err) {
          opts.onError(job, err);
          await queue.retryLater(job.id, job.attempts, String(err));
        }
      }
    } catch (err) {
      opts.onPollError(err);
    } finally {
      if (!stopped) timer = setTimeout(() => void tick(), opts.pollMs);
    }
  }

  timer = setTimeout(() => void tick(), opts.pollMs);
  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
  };
}
