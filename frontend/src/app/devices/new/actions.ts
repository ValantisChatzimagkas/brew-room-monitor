"use server";

import { refresh } from "next/cache";

import { getApi } from "@/lib/api/client";
import { type NewDeviceErrors, type NewDeviceInput, parseNewDevice } from "@/lib/devices";

/** `token` is the device's plaintext token, which the API returns only in this response. */
export type CreatedDevice = { id: number; name: string; token: string };
export type RegisterDeviceState = { errors: NewDeviceErrors; created: CreatedDevice | null };

/**
 * Registers a device and returns its token, shown once. A public POST endpoint: the input comes from the
 * client, so it isn't trusted. The token lives only in this return value: never log it, never put it in an
 * error or a redirect URL. `redirect`/`notFound` must not sit inside a `try`.
 */
export async function registerDevice(_prev: RegisterDeviceState, input: NewDeviceInput): Promise<RegisterDeviceState> {
  const api = await getApi();
  const parsed = parseNewDevice(input);
  if ("errors" in parsed) return { errors: parsed.errors, created: null };
  const { device } = parsed;

  const saved = await api.POST("/api/v1/devices", {
    body: { name: device.name, kind: device.kind, location_id: device.kind === "ambient" ? device.locationId : null },
  });
  // Names are unique per owner, matched exactly: "Shelf" and "shelf" are two devices.
  if (saved.response.status === 409) {
    return { errors: { name: "You already have a device with this name." }, created: null };
  }
  // A foreign or deleted room is a 422 like a missing one; the backend's reason isn't typed.
  if (saved.response.status === 422) {
    if (device.kind === "ambient") {
      return { errors: { room: "That room no longer exists. Reload the page and pick another." }, created: null };
    }
    return { errors: { form: "The API refused these values. Reload the page and try again." }, created: null };
  }
  if (saved.error) throw new Error("Failed to save to the API");
  refresh();
  return { errors: {}, created: { id: saved.data.id, name: saved.data.name, token: saved.data.token } };
}
