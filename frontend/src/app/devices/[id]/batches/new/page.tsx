import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { NewBatchForm } from "@/components/new-batch-form";
import { findDevice, getApi } from "@/lib/api/client";
import { blockingBatch, parseId } from "@/lib/history";

export default function NewBatchPage({ params }: PageProps<"/devices/[id]/batches/new">) {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
        <NewBatch params={params} />
      </Suspense>
    </main>
  );
}

async function NewBatch({ params }: Pick<PageProps<"/devices/[id]/batches/new">, "params">) {
  const { id: rawId } = await params;
  const id = parseId(rawId);
  if (id === null) notFound();

  const api = await getApi();
  const device = await findDevice(id);
  if (!device) notFound();
  const list = await api.GET("/api/v1/batches", { params: { query: { device_id: id, limit: 500 } } });
  if (list.error) throw new Error("Failed to load data from the API");
  const blocking = blockingBatch(list.data);

  return (
    <>
      <Link href={`/devices/${id}`} className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← {device.name}
      </Link>
      <h1 className="mb-6 text-2xl font-semibold">Start a batch</h1>
      {device.revoked_at !== null ? (
        <p className="text-muted-foreground">This device is revoked, so it can&apos;t start a batch.</p>
      ) : blocking?.ended_at === null ? (
        <p className="text-muted-foreground">
          <Link href={`/batches/${blocking.id}`} className="underline">
            {blocking.name}
          </Link>{" "}
          is already running on this device.
        </p>
      ) : (
        <NewBatchForm deviceId={id} />
      )}
    </>
  );
}
