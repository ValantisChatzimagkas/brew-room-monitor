import Link from "next/link";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { ReadingTime } from "@/components/reading-time";
import { StartBatchLink } from "@/components/start-batch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { YeastStatusBadge } from "@/components/yeast-status";
import { getApi, listDevices } from "@/lib/api/client";
import { ALL_BATCHES_LIMIT, runningBatches, startableDevices } from "@/lib/history";
import { formatAge } from "@/lib/time";
import { AMBIENT_CAVEAT, yeastRange, type YeastStatus, yeastStatus } from "@/lib/yeast";

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

  // Only a running batch with a range can have a status, so only those need the detail (its newest reading).
  const details = await Promise.all(
    list.data
      .filter((b) => b.ended_at === null && yeastRange(b) !== null)
      .map(async ({ id }) => {
        const result = await api.GET("/api/v1/batches/{batch_id}", { params: { path: { batch_id: id } } });
        if (result.error) throw new Error("Failed to load data from the API");
        return result.data;
      }),
  );
  const statuses = new Map<number, YeastStatus>();
  for (const detail of details) {
    const status = yeastStatus(detail, now);
    if (status !== null) statuses.set(detail.id, status);
  }
  const isAmbient = (deviceId: number) => devicesById.get(deviceId)?.kind === "ambient";
  const anyAmbientStatus = list.data.some((b) => statuses.has(b.id) && isAmbient(b.device_id));

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
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Batch</TableHead>
            <TableHead>Device</TableHead>
            <TableHead>Started</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Yeast range</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {list.data.map((b) => {
            const status = statuses.get(b.id);
            return (
              <TableRow key={b.id}>
                <TableCell>
                  <Link href={`/batches/${b.id}`} className="hover:underline">
                    {b.name}
                  </Link>
                </TableCell>
                <TableCell>{devicesById.get(b.device_id)?.name ?? `Device ${b.device_id}`}</TableCell>
                <TableCell>
                  <ReadingTime iso={b.started_at}>{formatAge(new Date(b.started_at), now)}</ReadingTime>
                </TableCell>
                <TableCell>
                  {b.ended_at === null ? (
                    <span className="text-primary">Running</span>
                  ) : (
                    <>
                      {"Ended "}
                      <ReadingTime iso={b.ended_at}>{formatAge(new Date(b.ended_at), now)}</ReadingTime>
                    </>
                  )}
                </TableCell>
                <TableCell>
                  {status !== undefined && <YeastStatusBadge status={status} ambient={isAmbient(b.device_id)} />}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {anyAmbientStatus && <p className="mt-2 text-sm text-muted-foreground">{AMBIENT_CAVEAT}</p>}
    </>
  );
}
