"use server";

import { refresh } from "next/cache";
import { notFound } from "next/navigation";

import { getApi } from "@/lib/api/client";
import { parseId } from "@/lib/history";

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
