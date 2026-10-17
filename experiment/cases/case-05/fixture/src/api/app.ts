import express, { Router } from "express";
import { validate } from "./validate";
import { InvalidTransitionError, type OrderService } from "../orders/orderService";

export interface AppDeps {
  orders: OrderService;
  requireUser: express.RequestHandler;
  requireService: express.RequestHandler;
}

export function orderRoutes(orders: OrderService): Router {
  const r = Router();

  // Called by the warehouse system (service credentials), not by the app.
  r.post(
    "/internal/orders/:id/status",
    validate({ status: { type: "string", oneOf: ["packed", "shipped", "delivered", "cancelled"] } }),
    async (req, res, next) => {
      try {
        await orders.updateStatus(req.params.id, req.body.status, req.auth.serviceName);
        res.status(204).end();
      } catch (err) {
        if (err instanceof InvalidTransitionError) {
          return res.status(409).json({ error: { code: "invalid_transition", message: err.message } });
        }
        next(err);
      }
    },
  );

  return r;
}

export function createApp(deps: AppDeps): express.Express {
  const app = express();
  app.use(express.json({ limit: "64kb" }));
  app.get("/healthz", (_req, res) => res.json({ ok: true }));
  app.use(deps.requireService, orderRoutes(deps.orders));
  // User-facing /v1 routes are mounted behind deps.requireUser.
  return app;
}
