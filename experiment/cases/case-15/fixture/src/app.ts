import express from "express";
import { errorHandler } from "./lib/errors";
import { requireUser } from "./middleware/auth";
import { activityRouter } from "./routes/activity";

export function buildApp() {
  const app = express();
  app.use(express.json({ limit: "100kb" }));
  app.get("/healthz", (_req, res) => res.send("ok"));
  app.use("/v1/activity", requireUser, activityRouter);
  app.use(errorHandler);
  return app;
}
