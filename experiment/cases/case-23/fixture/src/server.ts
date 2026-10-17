import express from "express";
import pg from "pg";
import { PgSessionRepo, PgUserRepo } from "./repos/pg.js";
import { authRouter } from "./routes/auth.js";
import { AuthService } from "./services/authService.js";

const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });
const auth = new AuthService(new PgUserRepo(pool), new PgSessionRepo(pool));

const app = express();
app.set("trust proxy", 1);
app.use(express.json({ limit: "16kb" }));
app.use(authRouter(auth));

app.listen(Number(process.env.PORT ?? 8080));
