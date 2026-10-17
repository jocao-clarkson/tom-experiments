export interface OutputOptions {
  json: boolean;
  isTTY: boolean;
  stdout?: NodeJS.WritableStream;
  stderr?: NodeJS.WritableStream;
}

/**
 * All command output goes through Output. Human progress lines are
 * suppressed in --json mode so stdout stays a single parseable document.
 */
export class Output {
  private readonly stdout: NodeJS.WritableStream;
  private readonly stderr: NodeJS.WritableStream;

  constructor(private readonly opts: OutputOptions) {
    this.stdout = opts.stdout ?? process.stdout;
    this.stderr = opts.stderr ?? process.stderr;
  }

  line(msg: string): void {
    if (!this.opts.json) this.stdout.write(msg + "\n");
  }

  ok(msg: string): void {
    this.line(this.opts.isTTY ? `\x1b[32m${msg}\x1b[0m` : msg);
  }

  warn(msg: string): void {
    this.stderr.write((this.opts.isTTY ? `\x1b[33m${msg}\x1b[0m` : msg) + "\n");
  }

  result(data: Record<string, unknown>, summary: string): void {
    if (this.opts.json) this.stdout.write(JSON.stringify(data) + "\n");
    else this.stdout.write(summary + "\n");
  }
}
