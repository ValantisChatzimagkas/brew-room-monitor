import { describe, expect, it } from "vitest";

import {
  autoBucket,
  breakGaps,
  type ChartPoint,
  isIsolated,
  isPartial,
  parseId,
  parseRange,
  rangeSince,
  toBucketPoints,
  toPoints,
} from "./history";

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

describe("toBucketPoints", () => {
  it("plots each bucket's average at its start, with its min-max as the range", () => {
    const buckets = [
      { bucket_start: "2026-01-01T12:00:00Z", avg_value: 12, min_value: 10, max_value: 14 },
      { bucket_start: "2026-01-01T13:00:00Z", avg_value: 20, min_value: 20, max_value: 20 },
    ];
    expect(toBucketPoints(buckets)).toEqual([
      { time: Date.parse("2026-01-01T12:00:00Z"), value: 12, range: [10, 14] },
      { time: Date.parse("2026-01-01T13:00:00Z"), value: 20, range: [20, 20] },
    ]);
  });
});

describe("autoBucket", () => {
  const HOUR = 60 * 60 * 1000;
  const DAY = 24 * HOUR;
  it.each([
    ["empty window", 0, "5m"],
    ["24h", 24 * HOUR, "5m"],
    ["3d", 3 * DAY, "15m"],
    ["7d", 7 * DAY, "30m"],
    ["28d", 28 * DAY, "3h"],
    ["183d", 183 * DAY, "12h"],
    ["1095d: nothing fits, the largest", 1095 * DAY, "1d"],
  ])("%s -> %s", (_, spanMs, expected) => {
    expect(autoBucket(spanMs)).toBe(expected);
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

const MIN = 60_000;
const at = (...minutes: number[]): ChartPoint[] => minutes.map((m, i) => ({ time: m * MIN, value: i }));
const gap = (minute: number) => ({ time: minute * MIN, value: null });

describe("breakGaps", () => {
  it.each([
    ["no points", [], []],
    ["one point", at(0), at(0)],
    ["two points", at(0, 10), at(0, 10)],
    ["regular 1-minute points", at(0, 1, 2, 3), at(0, 1, 2, 3)],
    ["one 10-minute gap", at(0, 1, 2, 12, 13), [...at(0, 1, 2), gap(7), ...at(0, 1, 2, 12, 13).slice(3)]],
    ["gap exactly 3x the median", at(0, 1, 2, 5, 6), at(0, 1, 2, 5, 6)],
    [
      "duplicate timestamps are ignored",
      at(0, 0, 1, 1, 2, 2, 12),
      [...at(0, 0, 1, 1, 2, 2), gap(7), ...at(0, 0, 1, 1, 2, 2, 12).slice(6)],
    ],
    ["all points share one timestamp", at(5, 5, 5), at(5, 5, 5)],
  ])("%s", (_, points, expected) => {
    const input = structuredClone(points);
    expect(breakGaps(points)).toEqual(expected);
    expect(points).toEqual(input);
  });
});

describe("isIsolated", () => {
  const [a, b, c] = at(0, 1, 2);
  it.each([
    ["one point", [a], 0, true],
    ["two adjacent points", [a, b], 0, false],
    ["a point between two gaps", [a, gap(1), b, gap(3), c], 2, true],
    ["first point followed by a gap", [a, gap(1), b, c], 0, true],
    ["last point after a gap", [a, b, gap(3), c], 3, true],
    ["a gap point", [a, gap(1), b], 1, false],
  ])("%s", (_, points, i, expected) => {
    expect(isIsolated(points, i)).toBe(expected);
  });
});
