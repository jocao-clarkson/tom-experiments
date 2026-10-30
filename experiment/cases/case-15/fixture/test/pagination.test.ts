import { config } from "../src/config";
import { decodeCursor, encodeCursor, parseLimit, toPage } from "../src/lib/pagination";

describe("pagination", () => {
  it("defaults and clamps limit", () => {
    expect(parseLimit(undefined)).toBe(config.paging.defaultLimit);
    expect(parseLimit("500")).toBe(config.paging.maxLimit);
    expect(() => parseLimit("0")).toThrow("limit must be a positive integer");
  });

  it("round-trips cursors", () => {
    const c = { createdAt: "2026-09-01T10:00:00.000Z", id: "a1" };
    expect(decodeCursor(encodeCursor(c))).toEqual(c);
    expect(() => decodeCursor("not-a-cursor")).toThrow("invalid cursor");
  });

  it("emits a next cursor only when an extra row was fetched", () => {
    const rows = [1, 2, 3].map((i) => ({ id: `n${i}`, created_at: new Date(2026, 0, 4 - i) }));
    expect(toPage(rows, 2).nextCursor).not.toBeNull();
    expect(toPage(rows, 3).nextCursor).toBeNull();
  });
});
