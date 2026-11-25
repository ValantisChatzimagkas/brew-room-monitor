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

/** Chart ticks show the time of day; above a day they add the date, since times then repeat across days. */
export function chartTickFormat(spanMs: number): Intl.DateTimeFormatOptions {
  if (spanMs <= DAY_MS) return { hour: "2-digit", minute: "2-digit" };
  return { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" };
}

const pad = (n: number) => String(n).padStart(2, "0");

/** A `datetime-local` value ("YYYY-MM-DDTHH:mm") for this instant in the runtime's time zone, floored to the minute. */
export function toLocalInput(date: Date): string {
  const day = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  return `${day}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** A `datetime-local` value read as the runtime's local time, as a UTC ISO string; `null` if it isn't one. */
export function localInputToUtc(value: string): string | null {
  // ECMAScript parses an offset-less date-time as local time, so anything carrying a zone is refused here.
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(value)) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}
