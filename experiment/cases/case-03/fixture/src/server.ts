import express, { type NextFunction, type Request, type Response } from "express";
import { Pool } from "pg";
import { loadConfig } from "./config.js";
import { OneTimeTokenRepo } from "./db/oneTimeTokenRepo.js";
import { UserRepo } from "./db/userRepo.js";
import { authRoutes } from "./http/routes.js";
import { JobQueue, startWorker } from "./jobs/queue.js";
import { HttpMailer, type Template } from "./mail/mailer.js";
import { EmailVerificationService, type AuditSink } from "./services/emailVerification.js";

function log(msg: string, fields: Record<string, unknown> = {}): void {
  console.log(JSON.stringify({ msg, ...fields, at: new Date().toISOString() }));
}

/** The load balancer appends the caller's address as the last X-Forwarded-For entry. */
function clientAddress(req: Request): string | undefined {
  const header = req.headers["x-forwarded-for"];
  const forwarded = Array.isArray(header) ? header.join(",") : header ?? "";
  const last = forwarded.split(",").pop()?.trim();
  return last || req.socket.remoteAddress;
}

const config = loadConfig();
const db = new Pool({ connectionString: config.databaseUrl });

const users = new UserRepo(db);
const tokens = new OneTimeTokenRepo(db, config.linkTtlMinutes);
const jobs = new JobQueue(db);
const mailer = new HttpMailer(config.mailEndpoint, config.mailApiKey, config.mailFrom);
const audit: AuditSink = { record: (event, data) => log("audit", { event, ...data }) };

const app = express();
app.use(express.json({ limit: "16kb" }));
app.use((req, res, next) => {
  const started = Date.now();
  res.on("finish", () => {
    log("request", {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      ms: Date.now() - started,
      client: clientAddress(req),
    });
  });
  next();
});

app.use(
  authRoutes({
    emailVerification: new EmailVerificationService(users, tokens, jobs, audit, config.publicBaseUrl),
  }),
);

app.use((err: unknown, req: Request, res: Response, _next: NextFunction) => {
  log("unhandled_error", { path: req.path, error: String(err) });
  res.status(500).json({ error: { code: "internal", message: "Something went wrong" } });
});

const stopWorker = startWorker(
  jobs,
  {
    send_mail: async (job) => {
      const { template, to, vars } = job.payload as { template: Template; to: string; vars: Record<string, string> };
      await mailer.send(template, to, vars);
    },
  },
  {
    pollMs: config.jobPollMs,
    onError: (job, err) =>
      log("job_failed", { id: job.id, kind: job.kind, attempts: job.attempts, payload: job.payload, error: String(err) }),
    onPollError: (err) => log("job_poll_failed", { error: String(err) }),
  },
);

const server = app.listen(config.port, () => log("listening", { port: config.port }));

process.on("SIGTERM", () => {
  stopWorker();
  server.close(() => void db.end());
});
