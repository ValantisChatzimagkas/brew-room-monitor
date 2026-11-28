import { Settings } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { BatchTable } from "@/components/batch-table";
import { MetricChart } from "@/components/metric-chart";
import { PartialNotice } from "@/components/partial-notice";
import { ReadingTime } from "@/components/reading-time";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { WaitingForReading } from "@/components/waiting-for-reading";
import { type Batch, type Device, findDevice, getApi, yeastStatuses } from "@/lib/api/client";
import {
  blockingBatch,
  breakGaps,
  DEFAULT_RANGE,
  parseId,
  parseRange,
  RANGES,
  rangeSince,
  READINGS_LIMIT,
  toPoints,
} from "@/lib/history";
import { DEVICE_KIND_LABEL } from "@/lib/devices";
import { METRIC_INFO, METRIC_ORDER } from "@/lib/metrics";
import { deviceStatus } from "@/lib/status";
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

  const [results, batchList] = await Promise.all([
    Promise.all(
      METRIC_ORDER.map(async (metric) => {
        const result = await api.GET("/api/v1/readings", {
          params: { query: { device_id: id, metric, since: since.toISOString(), limit: READINGS_LIMIT } },
        });
        if (result.error) throw new Error("Failed to load data from the API");
        return { metric, rows: result.data };
      }),
    ),
    api.GET("/api/v1/batches", { params: { query: { device_id: id, limit: BATCHES_LIMIT } } }),
  ]);
  if (batchList.error) throw new Error("Failed to load data from the API");
  const canStart = device.revoked_at === null && blockingBatch(batchList.data)?.ended_at !== null;
  const withRows = results.filter(({ rows }) => rows.length > 0);

  // An empty range can still hide older readings: only a device with none at all is waiting for its first.
  let waiting = false;
  if (withRows.length === 0) {
    const newest = await api.GET("/api/v1/readings", { params: { query: { device_id: id, limit: 1 } } });
    if (newest.error) throw new Error("Failed to load data from the API");
    waiting = deviceStatus(device, newest.data, now) === "waiting";
  }

  return (
    <>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">{device.name}</h1>
        <p className="text-muted-foreground">
          {DEVICE_KIND_LABEL[device.kind]} · {device.location?.name ?? "No room"}
        </p>
        {device.revoked_at !== null && (
          <span className="text-destructive">
            <ReadingTime iso={device.revoked_at}>Revoked {formatAge(new Date(device.revoked_at), now)}</ReadingTime>
          </span>
        )}
        <div className="mt-4 flex flex-wrap gap-2">
          {canStart && (
            <Link href={`/devices/${id}/batches/new`} className={buttonVariants()}>
              Start batch
            </Link>
          )}
          <Link href={`/devices/${id}/settings`} className={buttonVariants({ variant: "outline" })}>
            <Settings aria-hidden="true" />
            Settings
          </Link>
        </div>
      </header>
      <nav aria-label="Time range" className="mb-4 flex gap-2">
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
      {waiting ? (
        <WaitingForReading />
      ) : withRows.length === 0 ? (
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
                <MetricChart metric={metric} points={breakGaps(toPoints(rows))} from={since.getTime()} to={now.getTime()} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">Batches</h2>
        <Suspense fallback={<p className="text-muted-foreground">Loading batches…</p>}>
          <DeviceBatches device={device} batches={batchList.data} canStart={canStart} now={now} />
        </Suspense>
      </section>
    </>
  );
}

async function DeviceBatches({
  device,
  batches,
  canStart,
  now,
}: {
  device: Pick<Device, "id" | "name" | "kind">;
  batches: readonly Batch[];
  canStart: boolean;
  now: Date;
}) {
  const statuses = await yeastStatuses(batches, now);

  if (batches.length === 0) {
    return (
      <p className="text-muted-foreground">
        No batches yet.
        {canStart && (
          <>
            {" "}
            <Link href={`/devices/${device.id}/batches/new`} className="underline">
              Start the first batch
            </Link>
            .
          </>
        )}
      </p>
    );
  }

  return (
    <>
      {batches.length === BATCHES_LIMIT && (
        <p className="mb-2 text-sm text-muted-foreground">Showing the newest {BATCHES_LIMIT} batches.</p>
      )}
      <BatchTable
        batches={batches}
        statuses={statuses}
        devices={new Map([[device.id, { name: device.name, kind: device.kind }]])}
        showDevice={false}
        now={now}
      />
    </>
  );
}
