import express from "express";
import { Pool } from "pg";
import { KeyRepo } from "./keys/keyRepo";
import { KeyService } from "./keys/keyService";
import { keysRouter } from "./routes/keys";
import { logger } from "./lib/logger";

const db = new Pool({ connectionString: process.env.DATABASE_URL });
const repo = new KeyRepo(db);
const service = new KeyService(repo);

const app = express();
app.use(express.json());
app.use((req, _res, next) => {
  // The gateway verifies the session and forwards the actor as a signed header.
  (req as any).actor = JSON.parse(Buffer.from(req.header("x-actor") ?? "", "base64").toString() || "null");
  next();
});
app.use("/keys", keysRouter(service, repo));
app.use((err: any, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  res.status(err.status ?? 500).json({ error: err.status ? err.message : "internal_error" });
});

setInterval(() => {
  repo.expireDue().then((n) => n && logger.info("expired api keys", { count: n }));
}, 60 * 60 * 1000);

app.listen(8080);
