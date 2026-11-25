import type { Metric } from "@/lib/api/client";

type MetricInfo = { label: string; unit: string; decimals: number };

export const METRIC_INFO: Record<Metric, MetricInfo> = {
  temperature_c: { label: "Temperature", unit: "°C", decimals: 1 },
  humidity_pct: { label: "Humidity", unit: "%", decimals: 1 },
  pressure_hpa: { label: "Pressure", unit: "hPa", decimals: 1 },
  specific_gravity: { label: "Gravity", unit: "SG", decimals: 3 },
  battery_v: { label: "Battery", unit: "V", decimals: 2 },
};

/** Display and fetch order. Typecheck can't force a new metric in here; the test does. */
export const METRIC_ORDER: readonly Metric[] = [
  "temperature_c",
  "humidity_pct",
  "pressure_hpa",
  "specific_gravity",
  "battery_v",
];

export function formatValue(metric: Metric, value: number): string {
  const { unit, decimals } = METRIC_INFO[metric];
  return `${value.toFixed(decimals)} ${unit}`;
}

/** Rows in display order (the backend returns metric summaries by name). */
export function inMetricOrder<T extends { metric: Metric }>(rows: readonly T[]): T[] {
  return rows.toSorted((a, b) => METRIC_ORDER.indexOf(a.metric) - METRIC_ORDER.indexOf(b.metric));
}
