export const RANGES = ["6h", "24h"] as const;
export type Range = (typeof RANGES)[number];
export const DEFAULT_RANGE: Range = "24h";

/** API cap on `GET /readings` (`le=5000` in backend/app/routers/readings.py). */
export const READINGS_LIMIT = 5000;

const HOUR_MS = 60 * 60 * 1000;
const RANGE_HOURS: Record<Range, number> = { "6h": 6, "24h": 24 };

export type ChartPoint = { time: number; value: number };

export function parseRange(raw: string | string[] | undefined): Range {
  return RANGES.find((r) => r === raw) ?? DEFAULT_RANGE;
}

export function rangeSince(range: Range, now: Date): Date {
  return new Date(now.getTime() - RANGE_HOURS[range] * HOUR_MS);
}

export function parseDeviceId(raw: string): number | null {
  return /^\d+$/.test(raw) ? Number(raw) : null;
}

/** The API returns newest first; charts want oldest first. */
export function toPoints(newestFirst: readonly { recorded_at: string; value: number }[]): ChartPoint[] {
  return newestFirst.map((r) => ({ time: Date.parse(r.recorded_at), value: r.value })).reverse();
}

/** Rows come newest first, so a capped query has dropped the oldest rows in the range. */
export function isPartial(count: number): boolean {
  return count >= READINGS_LIMIT;
}
