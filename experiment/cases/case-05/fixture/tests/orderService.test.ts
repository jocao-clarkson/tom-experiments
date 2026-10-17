import { orderEvents, type StatusChanged } from "../src/orders/orderEvents";
import { InvalidTransitionError, OrderService } from "../src/orders/orderService";

function fakePool(status: string) {
  const queries: string[] = [];
  const client = {
    query: jest.fn(async (sql: string) => {
      queries.push(sql.trim().split(/\s+/)[0]);
      if (sql.startsWith("SELECT")) return { rowCount: 1, rows: [{ user_id: "u1", status }] };
      return { rowCount: 1, rows: [] };
    }),
    release: jest.fn(),
  };
  return { pool: { connect: jest.fn(async () => client) } as any, queries };
}

describe("OrderService.updateStatus", () => {
  afterEach(() => orderEvents.removeAllListeners());

  it("updates status and emits statusChanged", async () => {
    const { pool, queries } = fakePool("packed");
    const seen: StatusChanged[] = [];
    orderEvents.onStatusChanged((e) => {
      seen.push(e);
    });
    await new OrderService(pool).updateStatus("o1", "shipped", "warehouse");
    expect(seen).toEqual([{ orderId: "o1", userId: "u1", from: "packed", to: "shipped" }]);
    expect(queries).toEqual(["BEGIN", "SELECT", "UPDATE", "INSERT", "COMMIT"]);
  });

  it("rejects invalid transitions and rolls back", async () => {
    const { pool, queries } = fakePool("delivered");
    await expect(new OrderService(pool).updateStatus("o1", "shipped", "warehouse")).rejects.toBeInstanceOf(
      InvalidTransitionError,
    );
    expect(queries[queries.length - 1]).toBe("ROLLBACK");
  });
});
