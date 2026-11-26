"use server";

import { notFound, redirect } from "next/navigation";

import type { NewBatchState } from "@/app/devices/[id]/batches/new/actions";
import { getApi } from "@/lib/api/client";
import { isUnchangedStart, type NewBatchInput, parseId, parseNewBatch, previousBatch } from "@/lib/history";

/**
 * Saves a batch's name, start and yeast and returns to its page. A public POST endpoint: both arguments come
 * from the client, so neither is trusted. `redirect`/`notFound` must not sit inside a `try`.
 */
export async function editBatch(batchId: number, _prev: NewBatchState, input: NewBatchInput): Promise<NewBatchState> {
  const api = await getApi();
  const id = parseId(String(batchId));
  if (id === null) notFound();

  const path = { params: { path: { batch_id: id } } };
  // A foreign batch answers 404 like a missing one. The end is read here, not from the client, so a batch
  // ended in another tab is checked against its real end.
  const stored = await api.GET("/api/v1/batches/{batch_id}", path);
  if (stored.response.status === 404) notFound();
  if (stored.error) throw new Error("Failed to load data from the API");

  const parsed = parseNewBatch(input, new Date(), stored.data.ended_at);
  if ("errors" in parsed) return { errors: parsed.errors, conflict: null };
  // The form shows the start without seconds; sending it back untouched would move the window.
  const body = { ...parsed.body };
  if (isUnchangedStart(input.startedAt, stored.data.started_at)) delete body.started_at;

  const saved = await api.PATCH("/api/v1/batches/{batch_id}", { ...path, body });
  if (saved.response.status === 404) notFound();
  // The 409 doesn't say which batch it overlaps, so name it.
  if (saved.response.status === 409) {
    const list = await api.GET("/api/v1/batches", {
      params: { query: { device_id: stored.data.device_id, limit: 500 } },
    });
    if (list.error) throw new Error("Failed to load data from the API");
    const previous = previousBatch(list.data, stored.data);
    if (!previous) return { errors: { form: "This start overlaps another batch on this device." }, conflict: null };
    return { errors: {}, conflict: { id: previous.id, name: previous.name, endedAt: previous.ended_at } };
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
  redirect(`/batches/${id}`);
}
