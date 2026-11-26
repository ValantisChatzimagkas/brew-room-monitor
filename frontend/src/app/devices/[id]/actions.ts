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
