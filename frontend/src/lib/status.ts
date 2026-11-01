import { isStale } from "./time";

type DeviceStatus = "revoked" | "stale" | "ok";

/** Revoked wins over stale: a revoked device is silent by design, so showing both would hide that it was cut off on purpose. */
export function deviceStatus(
  device: { revoked_at: string | null },
  latest: readonly { recorded_at: string }[],
  now: Date,
): DeviceStatus {
  if (device.revoked_at) return "revoked";
  return isStale(latest, now) ? "stale" : "ok";
}
