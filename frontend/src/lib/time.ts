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

const oneDecimal = (n: number) => Math.round(n * 10) / 10; // 6.5 stays, 2.0 prints as 2

/** A span of whole seconds, e.g. "6.5 h"; hours up to 48 h, then days. */
export function formatDuration(seconds: number): string {
  const ms = seconds * 1000;
  if (ms === 0) return "0 min";
  if (ms < MINUTE_MS) return "< 1 min";
  if (ms < HOUR_MS) return `${Math.floor(ms / MINUTE_MS)} min`;
  if (ms < 2 * DAY_MS) return `${oneDecimal(ms / HOUR_MS)} h`;
  return `${oneDecimal(ms / DAY_MS)} d`;
}

/** A device is stale when even its newest reading is older than the threshold; no readings is not stale. */
export function isStale(latest: readonly { recorded_at: string }[], now: Date): boolean {
  if (latest.length === 0) return false;
  const newest = Math.max(...latest.map((r) => new Date(r.recorded_at).getTime()));
  return now.getTime() - newest > STALE_AFTER_MS;
}
