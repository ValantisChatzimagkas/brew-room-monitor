import Link from "next/link";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { BatchTable } from "@/components/batch-table";
import { getApi, listDevices, yeastStatuses } from "@/lib/api/client";

const BATCHES_LIMIT = 100;

export default function BatchesPage() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-semibold">Batches</h1>
      <Suspense fallback={<p className="text-muted-foreground">Loading batches…</p>}>
        <BatchList />
      </Suspense>
      <AutoRefresh />
    </main>
  );
}

async function BatchList() {
  const api = await getApi(); // must come before new Date(): it opts the render out of prerendering
  const now = new Date();
  const [list, devices] = await Promise.all([
    api.GET("/api/v1/batches", { params: { query: { limit: BATCHES_LIMIT } } }),
    listDevices(),
  ]);
  if (list.error) throw new Error("Failed to load data from the API");
  const devicesById = new Map(devices.map((d) => [d.id, d]));
  const statuses = await yeastStatuses(list.data, now);

  if (list.data.length === 0) {
    return (
      <p className="text-muted-foreground">
        No batches yet. Batches you start appear here, running ones first. Start one from a device on the{" "}
        <Link href="/" className="underline">
          Dashboard
        </Link>
        .
      </p>
    );
  }

  return (
    <>
      {list.data.length === BATCHES_LIMIT && (
        <p className="mb-2 text-sm text-muted-foreground">
          Showing {BATCHES_LIMIT} batches: running ones first, then the newest.
        </p>
      )}
      <BatchTable batches={list.data} statuses={statuses} devices={devicesById} showDevice now={now} />
    </>
  );
}
