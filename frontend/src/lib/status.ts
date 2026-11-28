import { isStale } from "./time";

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
