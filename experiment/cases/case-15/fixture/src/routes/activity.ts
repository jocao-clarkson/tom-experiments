import { Router } from "express";
import { userQuery } from "../db/pool";
import { enqueue } from "../jobs/queue";
import { decodeCursor, parseLimit, toPage } from "../lib/pagination";

export const activityRouter = Router();

interface ActivityRow {
  id: string;
  kind: string;
  summary: string;
  created_at: Date;
}

activityRouter.get("/", async (req, res, next) => {
  try {
    const limit = parseLimit(req.query.limit);
    const cursor = decodeCursor(req.query.cursor);
    const params: unknown[] = [limit + 1];
    let where = "";
    if (cursor) {
      params.push(cursor.createdAt, cursor.id);
      where = "WHERE (created_at, id) < ($2, $3)";
    }
    const { rows } = await userQuery<ActivityRow>(
      req.userId!,
      `SELECT id, kind, summary, created_at FROM activity ${where} ORDER BY created_at DESC, id DESC LIMIT $1`,
      params,
    );
    const page = toPage(rows, limit);
    res.json({ items: page.items, nextCursor: page.nextCursor });
  } catch (err) {
    next(err);
  }
});

activityRouter.delete("/", async (req, res, next) => {
  try {
    await enqueue("activity.purge", { userId: req.userId });
    res.status(202).end();
  } catch (err) {
    next(err);
  }
});
