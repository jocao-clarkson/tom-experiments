import express, { type NextFunction, type Request, type Response } from "express";
import pg from "pg";
import { FixedWindowLimiter } from "./lib/rateLimit.js";
import { logger } from "./lib/logger.js";
import { PgSessionRepo, PgUserRepo } from "./repos/pg.js";
import { authRouter } from "./routes/auth.js";
import { AuthService } from "./services/authService.js";

const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });
const auth = new AuthService(new PgUserRepo(pool), new PgSessionRepo(pool));
const loginLimiter = new FixedWindowLimiter(10, 60_000, new Map());

const app = express();
app.set("trust proxy", 1);
app.use(express.json({ limit: "16kb" }));
app.use(authRouter(auth, loginLimiter));

app.use((err: unknown, req: Request, res: Response, _next: NextFunction) => {
  logger.error("unhandled_error", { method: req.method, path: req.path, body: req.body, err: String(err) });
  res.status(500).json({ error: "internal" });
});

app.listen(Number(process.env.PORT ?? 8080));
