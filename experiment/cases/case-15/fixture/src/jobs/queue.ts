import { query } from "../db/pool";

export interface EnqueueOptions {
  delayMs?: number;
}

/** Jobs are picked up by the worker service, which polls `jobs` and retries failures with backoff. */
export async function enqueue(kind: string, payload: Record<string, unknown>, opts: EnqueueOptions = {}): Promise<void> {
  const runAfter = new Date(Date.now() + (opts.delayMs ?? 0));
  await query("INSERT INTO jobs (kind, payload, run_after) VALUES ($1, $2, $3)", [kind, JSON.stringify(payload), runAfter]);
}
