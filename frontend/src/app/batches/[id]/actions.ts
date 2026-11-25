"use server";

import { refresh } from "next/cache";
import { notFound } from "next/navigation";

import { getApi } from "@/lib/api/client";
import { endTimeError, parseId } from "@/lib/history";

export type EndBatchState = { error: string | null };

/**
 * Ends a running batch at `endedAtIso` (UTC, converted in the browser). A public POST endpoint: both
 * arguments come from the client, so neither is trusted. `redirect`/`notFound` must not sit inside a `try`.
 */
export async function endBatch(batchId: number, _prev: EndBatchState, endedAtIso: string): Promise<EndBatchState> {
  const api = await getApi();
  const id = parseId(String(batchId));
  if (id === null) notFound();
  if (typeof endedAtIso !== "string") return { error: "Enter a valid end time." };

  const path = { params: { path: { batch_id: id } } };
  // A foreign batch answers 404 like a missing one.
  const result = await api.GET("/api/v1/batches/{batch_id}", path);
  if (result.response.status === 404) notFound();
  if (result.error) throw new Error("Failed to load data from the API");
  // A stale tab must not overwrite a stored end: show it instead.
  if (result.data.ended_at !== null) {
    refresh();
    return { error: null };
  }

  const reason = endTimeError(endedAtIso, result.data.started_at, new Date());
  if (reason !== null) return { error: reason };

  const saved = await api.PATCH("/api/v1/batches/{batch_id}", { ...path, body: { ended_at: endedAtIso } });
  if (saved.response.status === 404) notFound();
  // Only a race or clock drift between containers gets past the check above; the backend's reason isn't typed.
  if (saved.response.status === 422) {
    return { error: "Couldn't end the batch at that time: it must be after the start and not in the future." };
  }
  if (saved.error) throw new Error("Failed to save to the API");
  refresh();
  return { error: null };
}
