import type { BatchCreate, BucketSize, ReadingBucket } from "@/lib/api/client";

export const RANGES = ["6h", "24h"] as const;
type Range = (typeof RANGES)[number];
export const DEFAULT_RANGE: Range = "24h";

export const BATCH_PERIODS = ["24h", "3d", "7d", "whole"] as const;
export type BatchPeriod = (typeof BATCH_PERIODS)[number];
export const DEFAULT_PERIOD: BatchPeriod = "whole";

export const GRANULARITIES = ["auto", "15m", "1h", "6h"] as const satisfies readonly ("auto" | BucketSize)[];
export type Granularity = (typeof GRANULARITIES)[number];
export const DEFAULT_GRANULARITY: Granularity = "auto";

/** API cap on `GET /readings` (`le=5000` in backend/app/routers/readings.py). */
export const READINGS_LIMIT = 5000;
/** API cap on `GET /readings/buckets` (`MAX_BUCKETS` in backend/app/routers/readings.py). */
export const MAX_BUCKETS = 5000;
/** Auto picks the finest bucket that keeps a chart at or under this many points. */
const AUTO_MAX_POINTS = 500;

const HOUR_MS = 60 * 60 * 1000;
type Hours = "6h" | "24h" | "3d" | "7d";
const RANGE_HOURS: Record<Hours, number> = { "6h": 6, "24h": 24, "3d": 72, "7d": 168 };
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

/** An exact match among `choices`, else `fallback`. */
export function parseRange<const T extends string>(
  raw: string | string[] | undefined,
  choices: readonly T[],
  fallback: T,
): T {
  return choices.find((c) => c === raw) ?? fallback;
}

export function rangeSince(range: Hours, now: Date): Date {
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

/**
 * A batch period's window: anchored to the batch's end (now while it runs), so "24h" of an ended batch is
 * its last day, and clipped to its start.
 */
export function batchWindow(
  batch: { started_at: string; ended_at: string | null },
  period: BatchPeriod,
  now: Date,
): { from: number; to: number } {
  const start = Date.parse(batch.started_at);
  const to = batch.ended_at === null ? now.getTime() : Date.parse(batch.ended_at);
  if (period === "whole") return { from: start, to };
  return { from: Math.max(start, rangeSince(period, new Date(to)).getTime()), to };
}

/** An ISO date-time with an explicit zone, as epoch ms; `null` if it isn't one. */
function parseZonedIso(iso: string): number | null {
  const ms = Date.parse(iso);
  return /(Z|[+-]\d{2}:\d{2})$/.test(iso) && Number.isFinite(ms) ? ms : null;
}

/**
 * Why an end time can't end this batch, in the user's words; `null` if it can. Mirrors the backend's
 * `_check_window` (end == start voids the batch, end == now is allowed), which stays the authority.
 */
export function endTimeError(endedAtIso: string, startedAtIso: string, now: Date): string | null {
  const end = parseZonedIso(endedAtIso);
  if (end === null) return "Enter a valid end time.";
  if (end < Date.parse(startedAtIso)) return "The end time is before the batch started.";
  if (end > now.getTime()) return "The end time is in the future.";
  return null;
}

export const NEW_BATCH_FIELDS = ["name", "startedAt", "yeastName", "yeastMin", "yeastMax"] as const;
export type NewBatchField = (typeof NEW_BATCH_FIELDS)[number];
/** `startedAt` is the UTC ISO string from `localInputToUtc`; the others are raw input values. */
export type NewBatchInput = Record<NewBatchField, string>;
export type NewBatchErrors = Partial<Record<NewBatchField | "form", string>>;

/** `BatchBase` caps `name` and `yeast_name` at 64 characters. */
const NAME_MAX = 64;

function isNewBatchInput(input: unknown): input is NewBatchInput {
  if (typeof input !== "object" || input === null) return false;
  return NEW_BATCH_FIELDS.every((field) => typeof Object.getOwnPropertyDescriptor(input, field)?.value === "string");
}

/** An empty value is `null`; anything else must be a finite number. */
function parseBound(raw: string): number | null | "invalid" {
  const value = raw.trim();
  if (value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : "invalid";
}

/**
 * The new batch's body, or why each field can't start it, in the user's words. Mirrors the backend's
 * `_check_window` (future start) and `_check_yeast_range` (one bound only, min above max; equal allowed) and
 * `BatchBase`'s length caps; the backend stays the authority. Rejects anything that isn't the form's shape.
 */
export function parseNewBatch(
  input: unknown,
  now: Date,
): { body: Omit<BatchCreate, "device_id" | "ended_at"> } | { errors: NewBatchErrors } {
  if (!isNewBatchInput(input)) return { errors: { form: "Reload the page and try again." } };
  const errors: NewBatchErrors = {};

  const name = input.name.trim();
  if (name === "") errors.name = "Enter a name.";
  else if (name.length > NAME_MAX) errors.name = "Keep the name to 64 characters.";

  const start = parseZonedIso(input.startedAt);
  if (start === null) errors.startedAt = "Enter a valid start time.";
  else if (start > now.getTime()) errors.startedAt = "The start time is in the future.";

  const yeastName = input.yeastName.trim();
  if (yeastName.length > NAME_MAX) errors.yeastName = "Keep the yeast name to 64 characters.";

  const min = parseBound(input.yeastMin);
  const max = parseBound(input.yeastMax);
  if (min === "invalid") errors.yeastMin = "Enter a number.";
  if (max === "invalid") errors.yeastMax = "Enter a number.";
  if (min === null && typeof max === "number") errors.yeastMin = "Enter both temperatures, or neither.";
  if (max === null && typeof min === "number") errors.yeastMax = "Enter both temperatures, or neither.";
  if (typeof min === "number" && typeof max === "number" && min > max) {
    errors.yeastMin = "The minimum is above the maximum.";
  }

  // The bound checks repeat what `errors` already says, so the types narrow.
  if (Object.keys(errors).length > 0 || min === "invalid" || max === "invalid") return { errors };
  return {
    body: {
      name,
      started_at: input.startedAt,
      yeast_name: yeastName === "" ? null : yeastName,
      yeast_min_temperature_c: min,
      yeast_max_temperature_c: max,
    },
  };
}

/**
 * The batch a new one on this device must start after: the running batch, else the ended batch that ends
 * last; `undefined` if none. A voided (zero-length) batch overlaps nothing, so it neither runs nor blocks a
 * start, and may sort anywhere; the first other row is the one, since non-empty batches can't overlap.
 */
export function blockingBatch<B extends { started_at: string; ended_at: string | null }>(
  newestFirst: readonly B[],
): B | undefined {
  return newestFirst.find((b) => b.ended_at === null || Date.parse(b.ended_at) !== Date.parse(b.started_at));
}

/**
 * A manual granularity if the API would accept it, else Auto. One bucket of headroom under the cap: the
 * backend measures an open batch's window a moment after this render does.
 */
export function pickBucket(granularity: Granularity, spanMs: number): BucketSize {
  if (granularity !== "auto" && bucketCount(spanMs, BUCKET_MS[granularity]) + 1 <= MAX_BUCKETS) return granularity;
  return autoBucket(spanMs);
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
