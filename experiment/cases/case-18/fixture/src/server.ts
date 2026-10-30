import express from "express";
import { Pool } from "pg";
import { KeyRepo } from "./keys/keyRepo";
import { KeyService } from "./keys/keyService";
import { VerifyCache } from "./keys/verifyCache";
import { keysRouter } from "./routes/keys";
import { logger } from "./lib/logger";

const db = new Pool({ connectionString: process.env.DATABASE_URL });
const repo = new KeyRepo(db);
const service = new KeyService(repo);
const cache = new VerifyCache((presented) => service.verify(presented));

const app = express();
app.use(express.json());
app.use((req, _res, next) => {
  // The gateway verifies the session and forwards the actor as a signed header.
  (req as any).actor = JSON.parse(Buffer.from(req.header("x-actor") ?? "", "base64").toString() || "null");
  next();
});

// Called by the gateway for every request that presents an API key.
app.post("/internal/verify", async (req, res, next) => {
  try {
    const key = await cache.verify(String(req.body.key ?? ""));
    if (!key) return res.status(401).json({ error: "invalid_key" });
    res.json({ keyId: key.id, orgId: key.orgId, ownerId: key.ownerId });
  } catch (err) {
    next(err);
  }
});

app.use("/keys", keysRouter(service, repo, cache));
app.use((err: any, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  res.status(err.status ?? 500).json({ error: err.status ? err.message : "internal_error" });
});

setInterval(() => {
  repo.expireDue().then((n) => n && logger.info("expired api keys", { count: n }));
}, 60 * 60 * 1000);

app.listen(8080);
