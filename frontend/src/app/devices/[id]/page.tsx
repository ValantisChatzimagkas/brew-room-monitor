import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { BatchSummaryTable } from "@/components/batch-summary-table";
import { BatchYeast } from "@/components/batch-yeast";
import { MetricChart } from "@/components/metric-chart";
import { PartialNotice } from "@/components/partial-notice";
import { ReadingTime } from "@/components/reading-time";
import { RekeyDeviceForm } from "@/components/rekey-device-form";
import { RevokeDeviceForm } from "@/components/revoke-device-form";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { type BatchDetail, findDevice, getApi } from "@/lib/api/client";
import {
  blockingBatch,
  DEFAULT_RANGE,
  parseId,
  parseRange,
  RANGES,
  rangeSince,
  READINGS_LIMIT,
  toPoints,
} from "@/lib/history";
import { METRIC_INFO, METRIC_ORDER } from "@/lib/metrics";
import { formatAge } from "@/lib/time";

const BATCHES_LIMIT = 10;

export default function DevicePage({ params, searchParams }: PageProps<"/devices/[id]">) {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Link href="/" className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← Dashboard
      </Link>
      <Suspense fallback={<p className="text-muted-foreground">Loading readings…</p>}>
        <DeviceDetail params={params} searchParams={searchParams} />
      </Suspense>
      <AutoRefresh />
    </main>
  );
}

async function DeviceDetail({
  params,
  searchParams,
}: Pick<PageProps<"/devices/[id]">, "params" | "searchParams">) {
  const { id: rawId } = await params;
  const id = parseId(rawId);
  if (id === null) notFound();

  const range = parseRange((await searchParams).range, RANGES, DEFAULT_RANGE);

  const api = await getApi(); // must come before new Date(): it opts the render out of prerendering
  const now = new Date();
  const since = rangeSince(range, now);
  const device = await findDevice(id);
  if (!device) notFound();

  const results = await Promise.all(
    METRIC_ORDER.map(async (metric) => {
      const result = await api.GET("/api/v1/readings", {
        params: { query: { device_id: id, metric, since: since.toISOString(), limit: READINGS_LIMIT } },
      });
      if (result.error) throw new Error("Failed to load data from the API");
      return { metric, rows: result.data };
    }),
  );
  const withRows = results.filter(({ rows }) => rows.length > 0);

  return (
    <>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">{device.name}</h1>
        <p className="text-muted-foreground">
          {device.kind} · {device.location?.name ?? "No room"}
        </p>
        {device.revoked_at !== null && (
          <span className="text-destructive">
            <ReadingTime iso={device.revoked_at}>Revoked {formatAge(new Date(device.revoked_at), now)}</ReadingTime>
          </span>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          <Link href={`/devices/${id}/edit`} className={buttonVariants({ variant: "outline" })}>
            Edit
          </Link>
          {/* Always rendered: the refresh() after a re-key clears `revoked_at`, and remounting this form would
              drop the new token on screen. */}
          <RekeyDeviceForm deviceId={id} deviceName={device.name} />
          {device.revoked_at === null && <RevokeDeviceForm deviceId={id} deviceName={device.name} />}
        </div>
        <nav aria-label="Time range" className="mt-4 flex gap-2">
          {RANGES.map((r) => (
            <Link
              key={r}
              href={`/devices/${id}?range=${r}`}
              aria-current={r === range ? "page" : undefined}
              className={buttonVariants({ variant: r === range ? "default" : "outline", size: "sm" })}
            >
              {r}
            </Link>
          ))}
        </nav>
      </header>
      {withRows.length === 0 ? (
        <p className="text-muted-foreground">No readings in the last {range}.</p>
      ) : (
        <div className="grid gap-6">
          {withRows.map(({ metric, rows }) => (
            <Card key={metric}>
              <CardHeader>
                <CardTitle>
                  {METRIC_INFO[metric].label} ({METRIC_INFO[metric].unit})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <PartialNotice count={rows.length} where="in this range" />
                <MetricChart metric={metric} points={toPoints(rows)} from={since.getTime()} to={now.getTime()} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">Batches</h2>
        <Suspense fallback={<p className="text-muted-foreground">Loading batches…</p>}>
          <DeviceBatches deviceId={id} now={now} revoked={device.revoked_at !== null} />
        </Suspense>
      </section>
    </>
  );
}

async function DeviceBatches({ deviceId, now, revoked }: { deviceId: number; now: Date; revoked: boolean }) {
  const api = await getApi();
  const list = await api.GET("/api/v1/batches", {
    params: { query: { device_id: deviceId, limit: BATCHES_LIMIT } },
  });
  if (list.error) throw new Error("Failed to load data from the API");
  const canStart = !revoked && blockingBatch(list.data)?.ended_at !== null;

  const batches = await Promise.all(
    list.data.map(async ({ id }) => {
      const result = await api.GET("/api/v1/batches/{batch_id}", { params: { path: { batch_id: id } } });
      if (result.error) throw new Error("Failed to load data from the API");
      return result.data;
    }),
  );

  return (
    <>
      {canStart && (
        <div className="mb-3">
          <Link href={`/devices/${deviceId}/batches/new`} className={buttonVariants({ size: "sm" })}>
            Start batch
          </Link>
        </div>
      )}
      {batches.length === 0 && <p className="text-muted-foreground">No batches yet</p>}
      {batches.length === BATCHES_LIMIT && (
        <p className="mb-2 text-sm text-muted-foreground">Showing the newest {BATCHES_LIMIT} batches.</p>
      )}
      <div className="grid gap-6">
        {batches.map((batch) => (
          <BatchCard key={batch.id} batch={batch} now={now} />
        ))}
      </div>
    </>
  );
}

function BatchCard({ batch, now }: { batch: BatchDetail; now: Date }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-2">
          <h3>
            <Link href={`/batches/${batch.id}`} className="hover:underline">
              {batch.name}
            </Link>
          </h3>
          {batch.ended_at === null && <span className="text-sm font-normal text-primary">Running</span>}
        </CardTitle>
        <CardDescription>
          Started <ReadingTime iso={batch.started_at}>{formatAge(new Date(batch.started_at), now)}</ReadingTime>
          {batch.ended_at === null ? (
            " · running"
          ) : (
            <>
              {" · ended "}
              <ReadingTime iso={batch.ended_at}>{formatAge(new Date(batch.ended_at), now)}</ReadingTime>
            </>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <BatchYeast batch={batch} />
        {batch.metrics.length === 0 ? (
          <p className="text-sm text-muted-foreground">No readings in this batch&apos;s window.</p>
        ) : (
          <BatchSummaryTable metrics={batch.metrics} now={now} />
        )}
      </CardContent>
    </Card>
  );
}
