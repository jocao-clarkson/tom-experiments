import request from "supertest";
import { buildApp } from "../src/app";

type Row = Record<string, unknown>;

function fakeDb(invoices: Row[]) {
  return {
    query: jest.fn(async (sql: string, params: unknown[]) => {
      if (sql.includes("FROM api_keys")) return { rows: [{ tenant_id: "t1" }] };
      if (sql.includes("FROM invoices")) {
        const [, limit, offset] = params as [string, number, number];
        return { rows: invoices.slice(offset, offset + limit) };
      }
      return { rows: [] };
    }),
  };
}

const invoices = Array.from({ length: 30 }, (_, i) => ({ id: `inv_${i}`, status: "open" }));

describe("GET /v1/invoices", () => {
  it("defaults to 25 rows", async () => {
    const app = buildApp({ db: fakeDb(invoices) as never, cursorSecret: "s" });
    const res = await request(app).get("/v1/invoices").set("authorization", "Bearer k");
    expect(res.status).toBe(200);
    expect(res.body.data).toHaveLength(25);
  });

  it("rejects limit over 100", async () => {
    const app = buildApp({ db: fakeDb(invoices) as never, cursorSecret: "s" });
    const res = await request(app).get("/v1/invoices?limit=101").set("authorization", "Bearer k");
    expect(res.status).toBe(400);
    expect(res.body.error.code).toBe("invalid_limit");
  });

  it("rejects unknown status", async () => {
    const app = buildApp({ db: fakeDb(invoices) as never, cursorSecret: "s" });
    const res = await request(app).get("/v1/invoices?status=late").set("authorization", "Bearer k");
    expect(res.body.error.code).toBe("invalid_status");
  });
});
