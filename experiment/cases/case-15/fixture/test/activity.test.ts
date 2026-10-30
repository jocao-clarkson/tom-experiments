import request from "supertest";
import jwt from "jsonwebtoken";
import { buildApp } from "../src/app";
import * as db from "../src/db/pool";

jest.mock("../src/db/pool");
jest.mock("jsonwebtoken");

describe("/v1/activity", () => {
  beforeEach(() => {
    jest.resetAllMocks();
    (jwt.verify as jest.Mock).mockReturnValue({ sub: "u1" });
  });

  it("runs the query as the caller and returns a cursor page", async () => {
    (db.userQuery as jest.Mock).mockResolvedValue({
      rows: [{ id: "a1", kind: "trip", summary: "x", created_at: new Date("2026-09-01T00:00:00Z") }],
    });
    const res = await request(buildApp()).get("/v1/activity?limit=5").set("authorization", "Bearer t");
    expect(res.status).toBe(200);
    expect((db.userQuery as jest.Mock).mock.calls[0][0]).toBe("u1");
    expect(res.body.nextCursor).toBeNull();
  });

  it("queues a purge and returns 202", async () => {
    (db.query as jest.Mock).mockResolvedValue({ rowCount: 1, rows: [] });
    const res = await request(buildApp()).delete("/v1/activity").set("authorization", "Bearer t");
    expect(res.status).toBe(202);
    expect((db.query as jest.Mock).mock.calls[0][1][0]).toBe("activity.purge");
  });
});
