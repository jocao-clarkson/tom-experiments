const REDACT = new Set(["secret", "plaintext", "password", "token", "authorization"]);

function redact(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, REDACT.has(k) ? "[redacted]" : redact(v)]),
    );
  }
  return value;
}

function emit(level: string, msg: string, fields: Record<string, unknown> = {}) {
  process.stdout.write(JSON.stringify({ level, msg, time: new Date().toISOString(), ...(redact(fields) as object) }) + "\n");
}

export const logger = {
  info: (msg: string, fields?: Record<string, unknown>) => emit("info", msg, fields),
  warn: (msg: string, fields?: Record<string, unknown>) => emit("warn", msg, fields),
  error: (msg: string, fields?: Record<string, unknown>) => emit("error", msg, fields),
  /** Security-relevant events; shipped to the audit index. */
  audit: (event: string, fields: Record<string, unknown>) => emit("audit", event, fields),
};
