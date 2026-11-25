import type { BucketSize, ReadingBucket } from "@/lib/api/client";

export const RANGES = ["6h", "24h"] as const;
type Range = (typeof RANGES)[number];
const DEFAULT_RANGE: Range = "24h";

/** API cap on `GET /readings` (`le=5000` in backend/app/routers/readings.py). */
export const READINGS_LIMIT = 5000;
/** API cap on `GET /readings/buckets` (`MAX_BUCKETS` in backend/app/routers/readings.py). */
export const MAX_BUCKETS = 5000;
/** Auto picks the finest bucket that keeps a chart at or under this many points. */
const AUTO_MAX_POINTS = 500;

const HOUR_MS = 60 * 60 * 1000;
const RANGE_HOURS: Record<Range, number> = { "6h": 6, "24h": 24 };
const MINUTE_MS = 60 * 1000;
const BUCKET_MS: Record<BucketSize, number> = {
  "5m": 5 * MINUTE_MS,
  "15m": 15 * MINUTE_MS,
  "30m": 30 * MINUTE_MS,
  "1h": HOUR_MS,
  "3h": 3 * HOUR_MS,
  "6h": 6 * HOUR_MS,
  "12h": 12 * HOUR_MS,
  "1d": 24 * HOUR_MS,
};
const isBucketSize = (key: string): key is BucketSize => key in BUCKET_MS;
/** Finest first. */
const BUCKET_SIZES = Object.keys(BUCKET_MS)
  .filter(isBucketSize)
  .toSorted((a, b) => BUCKET_MS[a] - BUCKET_MS[b]);

export type ChartPoint = { time: number; value: number };
/** A `null` value makes the chart's line stop and resume after it. */
export type ChartGap = { time: number; value: null };
/** A bucket's average, with its min-max as `range`. */
export type BucketPoint = ChartPoint & { range: [number, number] };

export function parseRange(raw: string | string[] | undefined): Range {
  return RANGES.find((r) => r === raw) ?? DEFAULT_RANGE;
}

export function rangeSince(range: Range, now: Date): Date {
  return new Date(now.getTime() - RANGE_HOURS[range] * HOUR_MS);
}

/** Ids are Postgres `integer` columns: a larger id makes the backend answer 500, so treat it as not found. */
const MAX_DB_ID = 2147483647;

export function parseId(raw: string): number | null {
  if (!/^\d+$/.test(raw)) return null;
  const id = Number(raw);
  return id <= MAX_DB_ID ? id : null;
}

/** The API returns newest first; charts want oldest first. */
export function toPoints(newestFirst: readonly { recorded_at: string; value: number }[]): ChartPoint[] {
  return newestFirst.map((r) => ({ time: Date.parse(r.recorded_at), value: r.value })).reverse();
}

/** Buckets come oldest first; each plots at its start. */
export function toBucketPoints(buckets: readonly ReadingBucket[]): BucketPoint[] {
  return buckets.map((b) => ({
    time: Date.parse(b.bucket_start),
    value: b.avg_value,
    range: [b.min_value, b.max_value],
  }));
}

/** The most grid-aligned buckets a window of this span can touch (same formula as the backend's `_bucket_count`). */
function bucketCount(spanMs: number, bucketMs: number): number {
  if (spanMs <= 0) return 0;
  return Math.ceil(spanMs / bucketMs) + 1;
}

/** The finest bucket size that keeps a chart of this span at or under ~500 points; the largest if none does. */
export function autoBucket(spanMs: number): BucketSize {
  const fits = BUCKET_SIZES.find((size) => bucketCount(spanMs, BUCKET_MS[size]) <= AUTO_MAX_POINTS);
  return fits ?? BUCKET_SIZES[BUCKET_SIZES.length - 1];
}

/** Rows come newest first, so a capped query has dropped the oldest rows in the range. */
export function isPartial(count: number): boolean {
  return count >= READINGS_LIMIT;
}

const GAP_FACTOR = 3;

/**
 * Breaks the line where readings stop for longer than 3× the median interval, so a chart doesn't bridge
 * an outage. Zero intervals (clockless readings share the server's receive time) don't count.
 */
export function breakGaps<P extends ChartPoint>(oldestFirst: readonly P[]): (P | ChartGap)[] {
  const intervals = oldestFirst
    .slice(1)
    .map((p, i) => p.time - oldestFirst[i].time)
    .filter((ms) => ms > 0)
    .toSorted((a, b) => a - b);
  if (intervals.length === 0) return [...oldestFirst];
  const mid = Math.floor(intervals.length / 2);
  const median = intervals.length % 2 === 1 ? intervals[mid] : (intervals[mid - 1] + intervals[mid]) / 2;

  return oldestFirst.flatMap((p, i) => {
    const prev = oldestFirst[i - 1];
    if (prev === undefined || p.time - prev.time <= GAP_FACTOR * median) return [p];
    return [{ time: (prev.time + p.time) / 2, value: null }, p];
  });
}

/** A reading with no reading beside it draws no line segment, so the chart shows it as a dot. */
export function isIsolated(points: readonly (ChartPoint | ChartGap)[], i: number): boolean {
  const hasValue = (j: number) => points[j] !== undefined && points[j].value !== null;
  return hasValue(i) && !hasValue(i - 1) && !hasValue(i + 1);
}
