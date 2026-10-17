import { createInterface } from "node:readline/promises";
import { UsageError } from "./errors.js";

export interface OutputContext {
  json: boolean;
  stdout: NodeJS.WritableStream;
  stdin: NodeJS.ReadableStream & { isTTY?: boolean };
}

export function printResult(ctx: OutputContext, data: Record<string, unknown>, rows?: string[][]): void {
  if (ctx.json) {
    ctx.stdout.write(JSON.stringify(data) + "\n");
    return;
  }
  for (const row of rows ?? Object.entries(data).map(([k, v]) => [k, String(v)])) {
    ctx.stdout.write(row.join("\t") + "\n");
  }
}

/** Ask a yes/no question. Refuses to guess when there is no terminal to ask. */
export async function confirm(ctx: OutputContext, question: string, assumeYes: boolean): Promise<boolean> {
  if (assumeYes) return true;
  if (!ctx.stdin.isTTY) {
    throw new UsageError(`${question} (stdin is not a terminal; pass --yes to proceed)`);
  }
  const rl = createInterface({ input: ctx.stdin, output: ctx.stdout });
  try {
    const answer = await rl.question(`${question} [y/N] `);
    return /^y(es)?$/i.test(answer.trim());
  } finally {
    rl.close();
  }
}
