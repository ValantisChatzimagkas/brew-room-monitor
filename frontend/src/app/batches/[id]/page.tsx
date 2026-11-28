import Link from "next/link";
import { notFound } from "next/navigation";
import { type ReactNode, Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { BatchCurrentState } from "@/components/batch-current-state";
import { BatchNotes } from "@/components/batch-notes";
import { BatchSummaryTable } from "@/components/batch-summary-table";
import { BatchYeast } from "@/components/batch-yeast";
import { EndBatchForm } from "@/components/end-batch-form";
import { MetricChart } from "@/components/metric-chart";
import { ReadingTime } from "@/components/reading-time";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { findDevice, getApi } from "@/lib/api/client";
import {
  autoBucket,
  BATCH_PERIODS,
  type BatchPeriod,
  batchWindow,
  breakGaps,
  DEFAULT_GRANULARITY,
  DEFAULT_PERIOD,
  GRANULARITIES,
  type Granularity,
  parseId,
  parseRange,
  pickBucket,
  toBucketPoints,
} from "@/lib/history";
import { inMetricOrder, METRIC_INFO } from "@/lib/metrics";
import { formatAge } from "@/lib/time";
import { yeastRange, yeastStatus } from "@/lib/yeast";

export default function BatchPage({ params, searchParams }: PageProps<"/batches/[id]">) {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Link href="/batches" className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← Batches
      </Link>
      <Suspense fallback={<p className="text-muted-foreground">Loading batch…</p>}>
        <BatchDetailView params={params} searchParams={searchParams} />
      </Suspense>
      <AutoRefresh />
    </main>
  );
}

async function BatchDetailView({
  params,
  searchParams,
}: Pick<PageProps<"/batches/[id]">, "params" | "searchParams">) {
  const { id: rawId } = await params;
  const id = parseId(rawId);
  if (id === null) notFound();

  const query = await searchParams;
  const period = parseRange(query.period, BATCH_PERIODS, DEFAULT_PERIOD);
  const requested = parseRange(query.granularity, GRANULARITIES, DEFAULT_GRANULARITY);

  const api = await getApi(); // must come before new Date(): it opts the render out of prerendering
  const now = new Date();
  // A foreign batch answers 404 like a missing one.
  const result = await api.GET("/api/v1/batches/{batch_id}", { params: { path: { batch_id: id } } });
  if (result.response.status === 404) notFound();
  if (result.error) throw new Error("Failed to load data from the API");
  const batch = result.data;
  const { from, to } = batchWindow(batch, period, now);
  const bucket = pickBucket(requested, to - from);
  // A manual size over the API's cap falls back to Auto, and the nav says so.
  const granularity: Granularity = bucket === requested ? requested : "auto";
  const since = period === "whole" ? undefined : new Date(from).toISOString();
  const href = (p: BatchPeriod, g: Granularity) => `/batches/${id}?period=${p}&granularity=${g}`;
  const [device, results] = await Promise.all([
    findDevice(batch.device_id),
    Promise.all(
      inMetricOrder(batch.metrics).map(async ({ metric }) => {
        const buckets = await api.GET("/api/v1/readings/buckets", {
          params: { query: { batch_id: id, metric, bucket, since } },
        });
        if (buckets.error) throw new Error("Failed to load data from the API");
        return { metric, rows: buckets.data };
      }),
    ),
  ]);
  const withRows = results.filter(({ rows }) => rows.length > 0);
  const range = yeastRange(batch) ?? undefined;
  const temperature = batch.metrics.find((m) => m.metric === "temperature_c");

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
        <div className="mt-3 flex flex-wrap items-start gap-2">
          <Link href={`/batches/${batch.id}/edit`} className={buttonVariants({ variant: "outline", size: "sm" })}>
            Edit
          </Link>
          {batch.ended_at === null && <EndBatchForm batchId={batch.id} />}
        </div>
      </header>
      {batch.ended_at === null && (
        <div className="mb-6">
          <BatchCurrentState
            status={yeastStatus(batch, now)}
            temperature={
              temperature === undefined
                ? null
                : { value: temperature.latest_value, recordedAt: temperature.latest_recorded_at }
            }
            range={yeastRange(batch)}
            ambient={device?.kind === "ambient"}
            now={now}
          />
        </div>
      )}
      <div className="mb-4 flex flex-wrap gap-x-6 gap-y-2">
        <nav aria-label="Period" className="flex gap-2">
          {BATCH_PERIODS.map((p) => (
            <PresetLink key={p} href={href(p, granularity)} active={p === period}>
              {p === "whole" ? "Whole batch" : p}
            </PresetLink>
          ))}
        </nav>
        <nav aria-label="Granularity" className="flex gap-2">
          {GRANULARITIES.map((g) =>
            g !== "auto" && pickBucket(g, to - from) !== g ? (
              <Button key={g} variant="outline" size="sm" disabled>
                {g}
              </Button>
            ) : (
              <PresetLink key={g} href={href(period, g)} active={g === granularity}>
                {g === "auto" ? `Auto (${autoBucket(to - from)})` : g}
              </PresetLink>
            ),
          )}
        </nav>
      </div>
      {batch.metrics.length === 0 ? (
        <p className="text-muted-foreground">No readings in this batch&apos;s window.</p>
      ) : (
        <>
          {withRows.length === 0 && <p className="text-muted-foreground">No readings in the selected period.</p>}
          <div className="grid gap-6">
            {withRows.map(({ metric, rows }) => (
              <Card key={metric}>
                <CardHeader>
                  <CardTitle>
                    {METRIC_INFO[metric].label} ({METRIC_INFO[metric].unit})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <MetricChart
                    metric={metric}
                    points={breakGaps(toBucketPoints(rows))}
                    from={from}
                    to={to}
                    yeastRange={metric === "temperature_c" ? range : undefined}
                  />
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
      <div className="mt-6">
        <BatchYeast batch={batch} />
        {range && <BatchNotes notes={batch.notes} range={range} ambient={device?.kind === "ambient"} />}
      </div>
      {batch.metrics.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-medium">Summary</h2>
          <BatchSummaryTable metrics={batch.metrics} now={now} />
        </section>
      )}
    </>
  );
}

function PresetLink({ href, active, children }: { href: string; active: boolean; children: ReactNode }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={buttonVariants({ variant: active ? "secondary" : "outline", size: "sm" })}
    >
      {children}
    </Link>
  );
}
