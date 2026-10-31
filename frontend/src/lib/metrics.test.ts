import { describe, expect, it } from "vitest";

import { formatValue, METRIC_INFO, METRIC_ORDER } from "./metrics";

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
