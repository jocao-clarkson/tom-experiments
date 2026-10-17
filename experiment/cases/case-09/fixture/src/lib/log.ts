let verbose = false;

const REDACT = new Set(["token", "authorization", "password"]);

export function setVerbose(on: boolean): void {
  verbose = on;
}

function redact(fields: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(fields)) {
    out[k] = REDACT.has(k.toLowerCase()) ? "[redacted]" : v;
  }
  return out;
}

/** Debug output goes to stderr and only with --verbose. Known secret keys are redacted. */
export function debug(message: string, fields: Record<string, unknown> = {}): void {
  if (!verbose) return;
  const extra = Object.keys(fields).length ? " " + JSON.stringify(redact(fields)) : "";
  process.stderr.write(`debug: ${message}${extra}\n`);
}
