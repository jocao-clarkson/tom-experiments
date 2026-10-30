export const ExitCode = {
  OK: 0,
  FAILURE: 1,
  USAGE: 2,
} as const;

export interface Streams {
  stdout: NodeJS.WritableStream;
  stderr: NodeJS.WritableStream;
}

/** Prints a result either as JSON (one line, stdout) or as human text. */
export function printResult(s: Streams, json: boolean, result: Record<string, unknown>, human: string): void {
  if (json) {
    s.stdout.write(JSON.stringify(result) + "\n");
  } else {
    s.stdout.write(human + "\n");
  }
}

export function printError(s: Streams, message: string): void {
  s.stderr.write(`error: ${message}\n`);
}

/** Used when the user declines a confirmation prompt. */
export function handleAbort(s: Streams): number {
  s.stderr.write("Aborted.\n");
  return ExitCode.FAILURE;
}
