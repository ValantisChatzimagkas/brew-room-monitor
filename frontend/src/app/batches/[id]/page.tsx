import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { BatchSummaryTable } from "@/components/batch-summary-table";
import { BatchYeast } from "@/components/batch-yeast";
import { MetricChart } from "@/components/metric-chart";
import { PartialNotice } from "@/components/partial-notice";
import { ReadingTime } from "@/components/reading-time";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { findDevice, getApi } from "@/lib/api/client";
import { breakGaps, parseId, READINGS_LIMIT, toPoints } from "@/lib/history";
import { inMetricOrder, METRIC_INFO } from "@/lib/metrics";
import { formatAge } from "@/lib/time";
import { yeastRange } from "@/lib/yeast";

export default function BatchPage({ params }: PageProps<"/batches/[id]">) {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Link href="/" className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← Dashboard
      </Link>
      <Suspense fallback={<p className="text-muted-foreground">Loading batch…</p>}>
        <BatchDetailView params={params} />
      </Suspense>
      <AutoRefresh />
    </main>
  );
}

async function BatchDetailView({ params }: Pick<PageProps<"/batches/[id]">, "params">) {
  const { id: rawId } = await params;
  const id = parseId(rawId);
  if (id === null) notFound();

  const api = await getApi(); // must come before new Date(): it opts the render out of prerendering
  const now = new Date();
  // A foreign batch answers 404 like a missing one.
  const result = await api.GET("/api/v1/batches/{batch_id}", { params: { path: { batch_id: id } } });
  if (result.response.status === 404) notFound();
  if (result.error) throw new Error("Failed to load data from the API");
  const batch = result.data;
  const [device, results] = await Promise.all([
    findDevice(batch.device_id),
    Promise.all(
      inMetricOrder(batch.metrics).map(async ({ metric }) => {
        const readings = await api.GET("/api/v1/readings", {
          params: { query: { batch_id: id, metric, limit: READINGS_LIMIT } },
        });
        if (readings.error) throw new Error("Failed to load data from the API");
        return { metric, rows: readings.data };
      }),
    ),
  ]);
  const withRows = results.filter(({ rows }) => rows.length > 0);
  const from = Date.parse(batch.started_at);
  const to = batch.ended_at ? Date.parse(batch.ended_at) : now.getTime();
  const range = yeastRange(batch) ?? undefined;

  return (
    <>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">{batch.name}</h1>
        <p className="text-muted-foreground">
          Started <ReadingTime iso={batch.started_at}>{formatAge(new Date(batch.started_at), now)}</ReadingTime>
          {batch.ended_at === null ? (
            " · running"
          ) : (
            <>
              {" · ended "}
              <ReadingTime iso={batch.ended_at}>{formatAge(new Date(batch.ended_at), now)}</ReadingTime>
            </>
          )}
          {" · "}
          <Link href={`/devices/${batch.device_id}`} className="hover:underline">
            {device?.name ?? `Device ${batch.device_id}`}
          </Link>
        </p>
        <div className="mt-4">
          <BatchYeast batch={batch} />
        </div>
      </header>
      {withRows.length === 0 ? (
        <p className="text-muted-foreground">No readings in this batch&apos;s window.</p>
      ) : (
        <>
          <div className="grid gap-6">
            {withRows.map(({ metric, rows }) => (
              <Card key={metric}>
                <CardHeader>
                  <CardTitle>
                    {METRIC_INFO[metric].label} ({METRIC_INFO[metric].unit})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <PartialNotice count={rows.length} where="in this batch" />
                  <MetricChart
                    metric={metric}
                    points={breakGaps(toPoints(rows))}
                    from={from}
                    to={to}
                    yeastRange={metric === "temperature_c" ? range : undefined}
                  />
                </CardContent>
              </Card>
            ))}
          </div>
          <section className="mt-8">
            <h2 className="mb-3 text-lg font-medium">Summary</h2>
            <BatchSummaryTable metrics={batch.metrics} now={now} />
          </section>
        </>
      )}
    </>
  );
}
