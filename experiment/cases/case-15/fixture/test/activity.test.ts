import request from "supertest";
import jwt from "jsonwebtoken";
import { buildApp } from "../src/app";
import * as db from "../src/db/pool";

jest.mock("../src/db/pool");
jest.mock("jsonwebtoken");

describe("GET /v1/activity", () => {
  beforeEach(() => {
    (jwt.verify as jest.Mock).mockReturnValue({ sub: "u1" });
  });

  it("scopes the query to the caller and returns a cursor page", async () => {
    (db.query as jest.Mock).mockResolvedValue({
      rows: [{ id: "a1", kind: "trip", summary: "x", created_at: new Date("2026-09-01T00:00:00Z") }],
    });
    const res = await request(buildApp()).get("/v1/activity?limit=5").set("authorization", "Bearer t");
    expect(res.status).toBe(200);
    expect((db.query as jest.Mock).mock.calls[0][1][0]).toBe("u1");
    expect(res.body.nextCursor).toBeNull();
  });
});
