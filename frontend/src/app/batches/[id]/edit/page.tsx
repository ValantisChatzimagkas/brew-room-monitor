import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { NewBatchForm } from "@/components/new-batch-form";
import { getApi } from "@/lib/api/client";
import { parseId } from "@/lib/history";

export default function EditBatchPage({ params }: PageProps<"/batches/[id]/edit">) {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
        <EditBatch params={params} />
      </Suspense>
    </main>
  );
}

async function EditBatch({ params }: Pick<PageProps<"/batches/[id]/edit">, "params">) {
  const { id: rawId } = await params;
  const id = parseId(rawId);
  if (id === null) notFound();

  const api = await getApi();
  // A foreign batch answers 404 like a missing one.
  const result = await api.GET("/api/v1/batches/{batch_id}", { params: { path: { batch_id: id } } });
  if (result.response.status === 404) notFound();
  if (result.error) throw new Error("Failed to load data from the API");
  const batch = result.data;
  const bound = (value: number | null | undefined) => String(value ?? "");

  return (
    <>
      <Link href={`/batches/${id}`} className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← {batch.name}
      </Link>
      <h1 className="mb-6 text-2xl font-semibold">Edit batch</h1>
      <NewBatchForm
        batch={{
          id: batch.id,
          name: batch.name,
          startedAt: batch.started_at,
          yeastName: batch.yeast_name ?? "",
          yeastMin: bound(batch.yeast_min_temperature_c),
          yeastMax: bound(batch.yeast_max_temperature_c),
        }}
      />
    </>
  );
}
