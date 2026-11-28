import Link from "next/link";
import { Suspense } from "react";

import { CannotStartBatch, runningBatches } from "@/components/start-batch";
import { getApi, listDevices } from "@/lib/api/client";
import { startableDevices } from "@/lib/history";

export default function ChooseDevicePage() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Link href="/batches" className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← Batches
      </Link>
      <h1 className="mb-6 text-2xl font-semibold">Start a batch</h1>
      <Suspense fallback={<p className="text-muted-foreground">Loading devices…</p>}>
        <DeviceChoice />
      </Suspense>
    </main>
  );
}

async function DeviceChoice() {
  const api = await getApi();
  // Running batches come first, so the 100 newest hold every device's running batch (at most one each).
  const [list, devices] = await Promise.all([
    api.GET("/api/v1/batches", { params: { query: { limit: 100 } } }),
    listDevices(),
  ]);
  if (list.error) throw new Error("Failed to load data from the API");
  const startable = startableDevices(devices, list.data);

  if (startable.length === 0) return <CannotStartBatch running={runningBatches(devices, list.data)} />;

  return (
    <>
      <p className="mb-3 text-muted-foreground">Pick the device that brews it.</p>
      <ul className="grid gap-2">
        {startable.map((d) => (
          <li key={d.id}>
            <Link href={`/devices/${d.id}/batches/new`} className="underline">
              {d.name}
            </Link>
          </li>
        ))}
      </ul>
    </>
  );
}
