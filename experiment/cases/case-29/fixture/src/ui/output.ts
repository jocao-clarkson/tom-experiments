import { formatJson } from "./format.js";

export interface OutputOptions {
  json: boolean;
  isTTY: boolean;
  stdout?: NodeJS.WritableStream;
  stderr?: NodeJS.WritableStream;
}

/** Command output: progress lines, warnings, and the final result. */
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

  fail(msg: string): void {
    this.line(this.opts.isTTY ? `\x1b[31m${msg}\x1b[0m` : msg);
  }

  warn(msg: string): void {
    this.stderr.write((this.opts.isTTY ? `\x1b[33m${msg}\x1b[0m` : msg) + "\n");
  }

  result(data: Record<string, unknown>, summary: string): void {
    if (this.opts.json) this.stdout.write(formatJson(data) + "\n");
    else this.stdout.write(summary + "\n");
  }
}
