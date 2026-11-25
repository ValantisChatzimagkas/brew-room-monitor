import { describe, expect, it } from "vitest";

import { isPartial, parseId, parseRange, rangeSince, toPoints } from "./history";

describe("parseRange", () => {
  it.each([
    ["6h", "6h"],
    ["24h", "24h"],
    [undefined, "24h"],
    ["", "24h"],
    ["7d", "24h"],
    ["6H", "24h"],
    [["6h", "24h"], "24h"],
    ["constructor", "24h"],
  ])("%j -> %s", (raw, expected) => {
    expect(parseRange(raw)).toBe(expected);
  });
});

describe("rangeSince", () => {
  const now = new Date("2026-01-01T12:00:00Z");

  it.each([
    ["6h", "2026-01-01T06:00:00.000Z"],
    ["24h", "2025-12-31T12:00:00.000Z"],
  ] as const)("%s", (range, expected) => {
    expect(rangeSince(range, now).toISOString()).toBe(expected);
  });
});

describe("parseId", () => {
  it.each([
    ["12", 12],
    ["abc", null],
    ["", null],
    ["1.5", null],
    ["-1", null],
    ["1e3", null],
    ["0x1", null],
    [" 12", null],
    ["2147483647", 2147483647],
    ["2147483648", null],
    ["1000000000000000000000", null],
  ])("%j -> %s", (raw, expected) => {
    expect(parseId(raw)).toBe(expected);
  });
});

describe("toPoints", () => {
  it("turns newest-first rows into oldest-first epoch points without touching the input", () => {
    const rows = [
      { recorded_at: "2026-01-01T12:02:00Z", value: 3 },
      { recorded_at: "2026-01-01T12:01:00Z", value: 2 },
      { recorded_at: "2026-01-01T12:00:00Z", value: 1 },
    ];
    expect(toPoints(rows)).toEqual([
      { time: Date.parse("2026-01-01T12:00:00Z"), value: 1 },
      { time: Date.parse("2026-01-01T12:01:00Z"), value: 2 },
      { time: Date.parse("2026-01-01T12:02:00Z"), value: 3 },
    ]);
    expect(rows.map((r) => r.value)).toEqual([3, 2, 1]);
  });

  it("returns nothing for no rows", () => {
    expect(toPoints([])).toEqual([]);
  });
});

describe("isPartial", () => {
  it.each([
    [0, false],
    [4999, false],
    [5000, true],
    [5001, true],
  ])("%d rows -> %s", (count, expected) => {
    expect(isPartial(count)).toBe(expected);
  });
});
