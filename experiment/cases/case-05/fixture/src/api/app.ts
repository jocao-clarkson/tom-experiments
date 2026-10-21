import express, { Router } from "express";
import type { OrderStatus } from "../orders/orderEvents";
import { InvalidTransitionError, type OrderService } from "../orders/orderService";

const SETTABLE: readonly OrderStatus[] = ["packed", "shipped", "delivered", "cancelled"];

export interface AppDeps {
  orders: OrderService;
  requireUser: express.RequestHandler;
  requireService: express.RequestHandler;
}

export function orderRoutes(orders: OrderService): Router {
  const r = Router();

  // Called by the warehouse system (service credentials), not by the app.
  r.post("/orders/:id/status", async (req, res, next) => {
    const status = req.body?.status;
    if (typeof status !== "string" || !SETTABLE.includes(status as OrderStatus)) {
      return res
        .status(400)
        .json({ error: { code: "invalid_request", fields: { status: `must be one of ${SETTABLE.join(", ")}` } } });
    }
    try {
      await orders.updateStatus(req.params.id, status as OrderStatus, req.auth.serviceName);
      res.status(204).end();
    } catch (err) {
      if (err instanceof InvalidTransitionError) {
        return res.status(409).json({ error: { code: "invalid_transition", message: err.message } });
      }
      next(err);
    }
  });

  return r;
}

export function createApp(deps: AppDeps): express.Express {
  const app = express();
  app.use(express.json({ limit: "64kb" }));
  app.get("/healthz", (_req, res) => res.json({ ok: true }));
  app.use("/internal", deps.requireService, orderRoutes(deps.orders));
  return app;
}
