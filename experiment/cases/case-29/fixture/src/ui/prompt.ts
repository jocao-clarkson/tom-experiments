import { createInterface } from "node:readline/promises";
import { AbortError } from "../errors.js";

export interface ConfirmOptions {
  yes: boolean;
  isTTY: boolean;
  input?: NodeJS.ReadableStream;
  output?: NodeJS.WritableStream;
}

/** Ask y/N. --yes skips the prompt; a non-interactive session without --yes aborts. */
export async function confirm(question: string, opts: ConfirmOptions): Promise<void> {
  if (opts.yes) return;
  if (!opts.isTTY) {
    throw new AbortError("refusing to continue without confirmation in a non-interactive session; pass --yes");
  }
  const rl = createInterface({ input: opts.input ?? process.stdin, output: opts.output ?? process.stderr });
  try {
    const answer = (await rl.question(`${question} [y/N] `)).trim().toLowerCase();
    if (answer !== "y" && answer !== "yes") throw new AbortError();
  } finally {
    rl.close();
  }
}
