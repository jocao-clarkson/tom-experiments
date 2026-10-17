import express from "express";
import type { Pool } from "pg";
import { requireApiKey } from "./middleware/auth";
import { errorMiddleware } from "./lib/errors";
import { customersRouter } from "./routes/customers";
import { invoicesRouter } from "./routes/invoices";

export interface AppDeps {
  db: Pool;
  cursorSecret: string;
}

export function buildApp(deps: AppDeps) {
  const app = express();
  app.use(express.json());
  app.use("/v1", requireApiKey(deps.db));
  app.use("/v1", customersRouter(deps));
  app.use("/v1", invoicesRouter(deps));
  app.use(errorMiddleware);
  return app;
}
