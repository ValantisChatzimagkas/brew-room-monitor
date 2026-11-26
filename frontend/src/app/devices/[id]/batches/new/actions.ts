"use server";

import { notFound, redirect } from "next/navigation";

import { findDevice, getApi } from "@/lib/api/client";
import { blockingBatch, type NewBatchErrors, type NewBatchInput, parseId, parseNewBatch } from "@/lib/history";

/** The batch a start conflicts with: running (`endedAt` null) or the ended one it must start after. */
export type ConflictBatch = { id: number; name: string; endedAt: string | null };
export type NewBatchState = { errors: NewBatchErrors; conflict: ConflictBatch | null };

/**
 * Starts a batch on a device and opens its page. A public POST endpoint: both arguments come from the
 * client, so neither is trusted. `redirect`/`notFound` must not sit inside a `try`.
 */
export async function startBatch(deviceId: number, _prev: NewBatchState, input: NewBatchInput): Promise<NewBatchState> {
  const api = await getApi();
  const id = parseId(String(deviceId));
  if (id === null) notFound();
  // A foreign device is not found like a missing one, before the POST.
  const device = await findDevice(id);
  if (!device) notFound();

  const parsed = parseNewBatch(input, new Date());
  if ("errors" in parsed) return { errors: parsed.errors, conflict: null };

  const saved = await api.POST("/api/v1/batches", { body: { ...parsed.body, device_id: id } });
  // A 409 is a revoked device or an overlap; ask the API which. Any overlap is a 409, not only a
  // running batch, so name the batch that blocks this start.
  if (saved.response.status === 409) {
    const now = await findDevice(id);
    if (!now) notFound();
    if (now.revoked_at !== null) {
      return { errors: { form: "This device is revoked, so it can't start a batch." }, conflict: null };
    }
    const list = await api.GET("/api/v1/batches", { params: { query: { device_id: id, limit: 500 } } });
    if (list.error) throw new Error("Failed to load data from the API");
    const blocking = blockingBatch(list.data);
    if (!blocking) return { errors: { form: "This batch overlaps another batch on this device." }, conflict: null };
    return { errors: {}, conflict: { id: blocking.id, name: blocking.name, endedAt: blocking.ended_at } };
  }
  // Only a check `parseNewBatch` doesn't mirror, or a race, gets here; the backend's reason isn't typed.
  if (saved.response.status === 422) {
    return {
      errors: {
        form: "The API refused these values. Check the yeast temperatures (−40 to 125 °C) and the start time.",
      },
      conflict: null,
    };
  }
  if (saved.error) throw new Error("Failed to save to the API");
  redirect(`/batches/${saved.data.id}`);
}
