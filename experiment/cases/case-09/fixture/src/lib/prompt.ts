import { createInterface } from "node:readline/promises";

/**
 * Ask a yes/no question on the terminal. When stdin is not a TTY (CI, pipes)
 * there is nobody to answer, so this resolves to false without reading.
 */
export async function confirm(question: string, stdin = process.stdin, stderr = process.stderr): Promise<boolean> {
  if (!stdin.isTTY) return false;
  const rl = createInterface({ input: stdin, output: stderr });
  try {
    const answer = (await rl.question(`${question} [y/N] `)).trim().toLowerCase();
    return answer === "y" || answer === "yes";
  } finally {
    rl.close();
  }
}
