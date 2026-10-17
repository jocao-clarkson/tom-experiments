import { Router } from "express";
import { query } from "../db/pool";
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
    const params: unknown[] = [req.userId, limit + 1];
    let where = "user_id = $1";
    if (cursor) {
      params.push(cursor.createdAt, cursor.id);
      where += " AND (created_at, id) < ($3, $4)";
    }
    const { rows } = await query<ActivityRow>(
      `SELECT id, kind, summary, created_at FROM activity WHERE ${where} ORDER BY created_at DESC, id DESC LIMIT $2`,
      params,
    );
    const page = toPage(rows, limit);
    res.json({ items: page.items, nextCursor: page.nextCursor });
  } catch (err) {
    next(err);
  }
});
