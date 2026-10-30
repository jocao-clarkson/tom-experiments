import type { Pool, PoolClient } from "pg";
import { orderEvents, type OrderStatus } from "./orderEvents";

const ALLOWED: Record<OrderStatus, OrderStatus[]> = {
  placed: ["packed", "cancelled"],
  packed: ["shipped", "cancelled"],
  shipped: ["delivered"],
  delivered: [],
  cancelled: [],
};

export class InvalidTransitionError extends Error {
  constructor(public readonly from: OrderStatus, public readonly to: OrderStatus) {
    super(`cannot move order from ${from} to ${to}`);
  }
}

export class OrderService {
  constructor(private readonly db: Pool) {}

  async updateStatus(orderId: string, to: OrderStatus, actor: string): Promise<void> {
    await this.transaction(async (tx) => {
      const res = await tx.query(`SELECT user_id, status FROM orders WHERE id = $1 FOR UPDATE`, [orderId]);
      if (res.rowCount === 0) throw new Error(`order ${orderId} not found`);
      const { user_id: userId, status: from } = res.rows[0] as { user_id: string; status: OrderStatus };
      if (!ALLOWED[from].includes(to)) throw new InvalidTransitionError(from, to);

      await tx.query(`UPDATE orders SET status = $2, updated_at = now() WHERE id = $1`, [orderId, to]);
      orderEvents.emitStatusChanged({ orderId, userId, from, to });
      await tx.query(
        `INSERT INTO order_status_history (order_id, from_status, to_status, actor) VALUES ($1, $2, $3, $4)`,
        [orderId, from, to, actor],
      );
    });
  }

  private async transaction<T>(fn: (tx: PoolClient) => Promise<T>): Promise<T> {
    const client = await this.db.connect();
    try {
      await client.query("BEGIN");
      const out = await fn(client);
      await client.query("COMMIT");
      return out;
    } catch (err) {
      await client.query("ROLLBACK");
      throw err;
    } finally {
      client.release();
    }
  }
}
