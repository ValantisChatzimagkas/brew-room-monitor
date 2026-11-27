"use server";

import { refresh } from "next/cache";
import { notFound, redirect } from "next/navigation";

import { findDevice, getApi, resolveRoom } from "@/lib/api/client";
import { type EditDeviceInput, type NewDeviceErrors, parseDeviceEdit } from "@/lib/devices";
import { parseId } from "@/lib/history";

export type EditDeviceState = { errors: NewDeviceErrors };

/**
 * Renames a device or moves it to another room, then opens its page. A public POST endpoint: both arguments
 * come from the client, so neither is trusted; the device's kind is read from the API, never from the input.
 * `redirect`/`notFound` must not sit inside a `try`.
 */
export async function updateDevice(
  deviceId: number,
  _prev: EditDeviceState,
  input: EditDeviceInput,
): Promise<EditDeviceState> {
  const api = await getApi();
  const id = parseId(String(deviceId));
  if (id === null) notFound();
  // A foreign device is not found like a missing one.
  const current = await findDevice(id);
  if (!current) notFound();

  const parsed = parseDeviceEdit(input, current.kind);
  if ("errors" in parsed) return { errors: parsed.errors };
  const { device } = parsed;
  const room = await resolveRoom(device);
  if ("errors" in room) return { errors: room.errors };

  // An in_vessel device's room isn't editable here, so it is never sent and stays as it is.
  const body = device.kind === "ambient" ? { name: device.name, location_id: room.locationId } : { name: device.name };
  const saved = await api.PATCH("/api/v1/devices/{device_id}", { params: { path: { device_id: id } }, body });
  if (saved.response.status === 404) notFound();
  // Names are unique per owner, matched exactly: "Shelf" and "shelf" are two devices.
  if (saved.response.status === 409) return { errors: { name: "You already have a device with this name." } };
  // A foreign or deleted room is a 422 like a missing one; the backend's reason isn't typed. A room this
  // action just created or found exists, so its 422 is something else.
  if (saved.response.status === 422) {
    if ("locationId" in device) {
      return { errors: { room: "That room no longer exists. Reload the page and pick another." } };
    }
    return { errors: { form: "The API refused these values. Reload the page and try again." } };
  }
  if (saved.error) throw new Error("Failed to save to the API");
  redirect(`/devices/${id}`);
}

/**
 * Cuts a device off: its token stops working and its readings stay. A public POST endpoint: the id comes
 * from the client, so it isn't trusted. A foreign device answers 404 like a missing one. Revoking an already
 * revoked device is a no-op. `redirect`/`notFound` must not sit inside a `try`.
 */
export async function revokeDevice(deviceId: number): Promise<null> {
  const api = await getApi();
  const id = parseId(String(deviceId));
  if (id === null) notFound();

  const saved = await api.POST("/api/v1/devices/{device_id}/revoke", { params: { path: { device_id: id } } });
  if (saved.response.status === 404) notFound();
  if (saved.error) throw new Error("Failed to save to the API");
  refresh();
  return null;
}

/** `token` is the device's new plaintext token, which the API returns only in this response. */
export type RekeyDeviceState = { token: string | null };

/**
 * Gives a device a new token, shown once: the old token stops working and a revoked device is re-enabled.
 * A public POST endpoint: the id comes from the client, so it isn't trusted. The token lives only in this
 * return value: never log it, never put it in an error or a redirect URL. `redirect`/`notFound` must not sit
 * inside a `try`.
 */
export async function rekeyDevice(deviceId: number): Promise<RekeyDeviceState> {
  const api = await getApi();
  const id = parseId(String(deviceId));
  if (id === null) notFound();

  const saved = await api.POST("/api/v1/devices/{device_id}/rotate", { params: { path: { device_id: id } } });
  if (saved.response.status === 404) notFound();
  if (saved.error) throw new Error("Failed to save to the API");
  refresh();
  return { token: saved.data.token };
}
