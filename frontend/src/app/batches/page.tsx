import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { BatchTable } from "@/components/batch-table";
import { StartBatchLink } from "@/components/start-batch";
import { getApi, listDevices, yeastStatuses } from "@/lib/api/client";
import { ALL_BATCHES_LIMIT, runningBatches, startableDevices } from "@/lib/history";

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
    api.GET("/api/v1/batches", { params: { query: { limit: ALL_BATCHES_LIMIT } } }),
    listDevices(),
  ]);
  if (list.error) throw new Error("Failed to load data from the API");
  const devicesById = new Map(devices.map((d) => [d.id, d]));
  const statuses = await yeastStatuses(list.data, now);

  const startBatch = (
    <StartBatchLink startable={startableDevices(devices, list.data)} running={runningBatches(devices, list.data)} />
  );

  if (list.data.length === 0) {
    return (
      <div className="grid justify-items-start gap-4">
        <p className="text-muted-foreground">No batches yet. Batches you start appear here, running ones first.</p>
        {startBatch}
      </div>
    );
  }

  return (
    <>
      <div className="mb-4 flex justify-end text-right">{startBatch}</div>
      {list.data.length === ALL_BATCHES_LIMIT && (
        <p className="mb-2 text-sm text-muted-foreground">
          Showing {ALL_BATCHES_LIMIT} batches: running ones first, then the newest.
        </p>
      )}
      <BatchTable batches={list.data} statuses={statuses} devices={devicesById} showDevice now={now} />
    </>
  );
}
