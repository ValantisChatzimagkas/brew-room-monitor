import Link from "next/link";
import { Suspense } from "react";

import { ReadingTime } from "@/components/reading-time";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getApi, listDevices } from "@/lib/api/client";
import { formatAge } from "@/lib/time";

const BATCHES_LIMIT = 100;

export default function BatchesPage() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-semibold">Batches</h1>
      <Suspense fallback={<p className="text-muted-foreground">Loading batches…</p>}>
        <BatchList />
      </Suspense>
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
  const deviceNames = new Map(devices.map((d) => [d.id, d.name]));

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
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Batch</TableHead>
            <TableHead>Device</TableHead>
            <TableHead>Started</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {list.data.map((b) => (
            <TableRow key={b.id}>
              <TableCell>
                <Link href={`/batches/${b.id}`} className="hover:underline">
                  {b.name}
                </Link>
              </TableCell>
              <TableCell>{deviceNames.get(b.device_id) ?? `Device ${b.device_id}`}</TableCell>
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
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}
