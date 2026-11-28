import { formatAge, isStale } from "./time";

/** A device or batch whose newest reading is stale, or that has none: the same words everywhere. */
export const NO_RECENT_DATA = "No recent data";

type DeviceStatus = "revoked" | "waiting" | "stale" | "ok";

/**
 * Revoked wins over waiting and stale: a revoked device is silent by design (and can't send its first
 * reading), so showing either would hide that it was cut off on purpose. `latest` empty means it never sent one.
 */
export function deviceStatus(
  device: { revoked_at: string | null },
  latest: readonly { recorded_at: string }[],
  now: Date,
): DeviceStatus {
  if (device.revoked_at) return "revoked";
  if (latest.length === 0) return "waiting";
  return isStale(latest, now) ? "stale" : "ok";
}

/** `NO_RECENT_DATA` and since when, from the newest of `latest` (as `isStale` decides); empty says only the words. */
export function noRecentDataText(latest: readonly { recorded_at: string }[], now: Date): string {
  if (latest.length === 0) return NO_RECENT_DATA;
  const newest = Math.max(...latest.map((r) => new Date(r.recorded_at).getTime()));
  return `${NO_RECENT_DATA} · last reading ${formatAge(new Date(newest), now)}`;
}
