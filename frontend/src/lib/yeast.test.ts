import { describe, expect, it } from "vitest";

import type { BatchDetail } from "./api/client";
import { formatValue } from "./metrics";
import { formatDuration, STALE_AFTER_MS } from "./time";
import { noteText, yeastPosition, yeastSplit, yeastStatus } from "./yeast";

describe("yeastSplit", () => {
  it.each([
    ["no readings", [0, 0, 0], [false, false, false]],
    ["all inside", [0, 5400, 0], [false, false, false]],
    ["some below", [600, 5400, 0], [true, false, false]],
    ["some above", [0, 5400, 60], [false, false, true]],
    ["below and above, none inside", [600, 0, 600], [true, false, true]],
  ])("%s", (_, [below_s, inside_s, above_s], flagged) => {
    expect(yeastSplit({ below_s, inside_s, above_s })).toEqual([
      { label: "below", seconds: below_s, flagged: flagged[0] },
      { label: "inside", seconds: inside_s, flagged: flagged[1] },
      { label: "above", seconds: above_s, flagged: flagged[2] },
    ]);
  });
});

describe("yeastPosition", () => {
  it.each([
    [{ min: 18, max: 22 }, 17.9, "below"],
    [{ min: 18, max: 22 }, 18, "inside"],
    [{ min: 18, max: 22 }, 20, "inside"],
    [{ min: 18, max: 22 }, 22, "inside"],
    [{ min: 18, max: 22 }, 22.1, "above"],
    [{ min: 20, max: 20 }, 20, "inside"],
    [{ min: 20, max: 20 }, 19.9, "below"],
    [{ min: 20, max: 20 }, 20.1, "above"],
  ])("%j, %d -> %s", (range, value, expected) => {
    expect(yeastPosition(value, range)).toBe(expected);
  });
});

describe("yeastStatus", () => {
  const now = new Date("2026-01-01T12:00:00Z");
  const reading = (metric: BatchDetail["metrics"][number]["metric"], value: number, ageMs: number) => ({
    metric,
    count: 1,
    min_value: value,
    max_value: value,
    avg_value: value,
    latest_value: value,
    latest_recorded_at: new Date(now.getTime() - ageMs).toISOString(),
  });
  const temp = (value: number, ageMs = 60_000) => [reading("temperature_c", value, ageMs)];
  const running = { ended_at: null, yeast_min_temperature_c: 18, yeast_max_temperature_c: 22 };

  it.each([
    ["in range", running, temp(20), "in_range"],
    ["exactly at min", running, temp(18), "in_range"],
    ["exactly at max", running, temp(22), "in_range"],
    ["below min", running, temp(17.9), "too_cold"],
    ["above max", running, temp(22.1), "too_warm"],
    ["exactly at the stale threshold", running, temp(20, STALE_AFTER_MS), "in_range"],
    ["just past the stale threshold", running, temp(20, STALE_AFTER_MS + 1000), "no_recent_data"],
    ["stale and out of range", running, temp(30, STALE_AFTER_MS + 1000), "no_recent_data"],
    ["no temperature metric", running, [reading("humidity_pct", 60, 60_000)], "no_recent_data"],
    ["no readings", running, [], "no_recent_data"],
    ["no range", { ...running, yeast_min_temperature_c: null, yeast_max_temperature_c: null }, temp(20), null],
    ["ended batch", { ...running, ended_at: "2026-01-01T11:00:00Z" }, temp(20), null],
  ] as const)("%s", (_, batch, metrics, expected) => {
    expect(yeastStatus({ ...batch, metrics: [...metrics] }, now)).toBe(expected);
  });
});

describe("noteText", () => {
  const range = { min: 18, max: 22 };
  const temp = (value: number) => formatValue("temperature_c", value);
  it.each([
    ["early_hot", 21600, 5, [formatDuration(21600), temp(27)], true],
    ["early_warm", 21600, null, [formatDuration(21600), temp(22)], true],
    ["late_cold", 86400, null, [formatDuration(86400), temp(18)], true],
    ["sharp_drop", 43200, 4.5, [formatDuration(43200), temp(4.5)], true],
    ["late_warm", 3600, null, [formatDuration(3600), temp(22)], true],
    ["in_range", 7200, null, [temp(18), temp(22)], false],
  ] as const)("%s", (code, duration_s, delta_c, numbers, hedged) => {
    const text = noteText({ code, duration_s, delta_c }, range);
    for (const n of numbers) expect(text).toContain(n);
    expect(/\bmay\b/.test(text)).toBe(hedged);
  });

  it.each(["early_hot", "sharp_drop"] as const)("%s without delta_c throws (broken contract)", (code) => {
    expect(() => noteText({ code, duration_s: 3600, delta_c: null }, range)).toThrow();
  });
});
