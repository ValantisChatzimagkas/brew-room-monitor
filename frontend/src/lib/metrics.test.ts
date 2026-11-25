import { describe, expect, it } from "vitest";

import type { Metric } from "@/lib/api/client";

import { formatValue, inMetricOrder, METRIC_INFO, METRIC_ORDER } from "./metrics";

describe("formatValue", () => {
  it.each([
    ["temperature_c", 21.44, "21.4 °C"],
    ["humidity_pct", 55, "55.0 %"],
    ["pressure_hpa", 1013.25, "1013.3 hPa"],
    ["specific_gravity", 1.05, "1.050 SG"],
    ["battery_v", 3.7, "3.70 V"],
  ] as const)("%s %d", (metric, value, expected) => {
    expect(formatValue(metric, value)).toBe(expected);
  });
});

it("METRIC_ORDER lists every metric exactly once", () => {
  expect([...METRIC_ORDER].sort()).toEqual(Object.keys(METRIC_INFO).sort());
});

describe("inMetricOrder", () => {
  it.each<[string, Metric[], Metric[]]>([
    [
      "backend (alphabetical) order",
      ["battery_v", "humidity_pct", "pressure_hpa", "specific_gravity", "temperature_c"],
      ["temperature_c", "humidity_pct", "pressure_hpa", "specific_gravity", "battery_v"],
    ],
    ["a subset in reverse", ["battery_v", "specific_gravity", "temperature_c"], ["temperature_c", "specific_gravity", "battery_v"]],
    ["empty", [], []],
  ])("%s", (_, input, expected) => {
    expect(inMetricOrder(input.map((metric) => ({ metric }))).map((r) => r.metric)).toEqual(expected);
  });
});
