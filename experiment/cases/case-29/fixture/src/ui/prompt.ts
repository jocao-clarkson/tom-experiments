import { createInterface } from "node:readline/promises";

export interface ConfirmOptions {
  yes: boolean;
  isTTY: boolean;
  input?: NodeJS.ReadableStream;
  output?: NodeJS.WritableStream;
}

/**
 * Ask a y/N question. Resolves true when --yes was given or the user answers
 * y/yes. Resolves false otherwise, including when there is no terminal to ask on.
 */
export async function confirm(question: string, opts: ConfirmOptions): Promise<boolean> {
  if (opts.yes) return true;
  if (!opts.isTTY) return false;
  const rl = createInterface({ input: opts.input ?? process.stdin, output: opts.output ?? process.stderr });
  try {
    const answer = (await rl.question(`${question} [y/N] `)).trim().toLowerCase();
    return answer === "y" || answer === "yes";
  } finally {
    rl.close();
  }
}
