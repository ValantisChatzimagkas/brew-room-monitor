export const STALE_AFTER_MS = 30 * 60_000;

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

export function formatAge(recordedAt: Date, now: Date): string {
  const ms = now.getTime() - recordedAt.getTime();
  if (ms < MINUTE_MS) return "just now"; // includes slightly-future timestamps (device clock skew)
  if (ms < HOUR_MS) return `${Math.floor(ms / MINUTE_MS)} min ago`;
  if (ms < DAY_MS) return `${Math.floor(ms / HOUR_MS)} h ago`;
  return `${Math.floor(ms / DAY_MS)} d ago`;
}

/** A device is stale when even its newest reading is older than the threshold; no readings is not stale. */
export function isStale(latest: readonly { recorded_at: string }[], now: Date): boolean {
  if (latest.length === 0) return false;
  const newest = Math.max(...latest.map((r) => new Date(r.recorded_at).getTime()));
  return now.getTime() - newest > STALE_AFTER_MS;
}

/** Chart ticks show the time of day; above a day they add the date, since times then repeat across days. */
export function chartTickFormat(spanMs: number): Intl.DateTimeFormatOptions {
  if (spanMs <= DAY_MS) return { hour: "2-digit", minute: "2-digit" };
  return { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" };
}
