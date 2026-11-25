import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { MetricChart } from "@/components/metric-chart";
import { ReadingTime } from "@/components/reading-time";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { type BatchDetail, getApi } from "@/lib/api/client";
import { isPartial, parseDeviceId, parseRange, RANGES, rangeSince, READINGS_LIMIT, toPoints } from "@/lib/history";
import { formatValue, inMetricOrder, METRIC_INFO, METRIC_ORDER } from "@/lib/metrics";
import { formatAge } from "@/lib/time";
import { yeastSplit } from "@/lib/yeast";

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
  const id = parseDeviceId(rawId);
  if (id === null) notFound();

  const range = parseRange((await searchParams).range);

  const api = await getApi(); // must come before new Date(): it opts the render out of prerendering
  const now = new Date();
  const since = rangeSince(range, now);
  // No GET /devices/{id}: list at the route's max limit and find. A device beyond the first 500 by name 404s.
  const devices = await api.GET("/api/v1/devices", { params: { query: { limit: 500 } } });
  if (devices.error) throw new Error("Failed to load data from the API");
  const device = devices.data.find((d) => d.id === id);
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
                {isPartial(rows.length) && (
                  <p className="mb-2 text-sm text-stale">
                    Partial: showing only the newest {READINGS_LIMIT} readings in this range.
                  </p>
                )}
                <MetricChart metric={metric} points={toPoints(rows)} from={since.getTime()} to={now.getTime()} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
      <section className="mt-8">
        <h2 className="mb-3 text-lg font-medium">Batches</h2>
        <Suspense fallback={<p className="text-muted-foreground">Loading batches…</p>}>
          <DeviceBatches deviceId={id} now={now} />
        </Suspense>
      </section>
    </>
  );
}

async function DeviceBatches({ deviceId, now }: { deviceId: number; now: Date }) {
  const api = await getApi();
  const list = await api.GET("/api/v1/batches", {
    params: { query: { device_id: deviceId, limit: BATCHES_LIMIT } },
  });
  if (list.error) throw new Error("Failed to load data from the API");
  if (list.data.length === 0) return <p className="text-muted-foreground">No batches yet</p>;

  const batches = await Promise.all(
    list.data.map(async ({ id }) => {
      const result = await api.GET("/api/v1/batches/{batch_id}", { params: { path: { batch_id: id } } });
      if (result.error) throw new Error("Failed to load data from the API");
      return result.data;
    }),
  );

  return (
    <>
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
          <h3>{batch.name}</h3>
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
        <div className="mb-4 text-sm">
          <YeastLine batch={batch} />
          {batch.yeast_fit !== null && (
            <p className="tabular-nums">
              {yeastSplit(batch.yeast_fit).map((item, i) => (
                <span key={item.label}>
                  {i > 0 && " · "}
                  <span className={item.flagged ? "font-medium text-out-of-range" : undefined}>
                    {item.count} {item.label}
                  </span>
                </span>
              ))}
            </p>
          )}
        </div>
        {batch.metrics.length === 0 ? (
          <p className="text-sm text-muted-foreground">No readings in this batch&apos;s window.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Metric</TableHead>
                <TableHead>Min</TableHead>
                <TableHead>Max</TableHead>
                <TableHead>Average</TableHead>
                <TableHead>Latest</TableHead>
                <TableHead>Readings</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {inMetricOrder(batch.metrics).map((m) => (
                <TableRow key={m.metric}>
                  <TableCell>{METRIC_INFO[m.metric].label}</TableCell>
                  <TableCell className="tabular-nums">{formatValue(m.metric, m.min_value)}</TableCell>
                  <TableCell className="tabular-nums">{formatValue(m.metric, m.max_value)}</TableCell>
                  <TableCell className="tabular-nums">{formatValue(m.metric, m.avg_value)}</TableCell>
                  <TableCell className="tabular-nums">
                    {formatValue(m.metric, m.latest_value)}{" "}
                    <span className="text-muted-foreground">
                      <ReadingTime iso={m.latest_recorded_at}>{formatAge(new Date(m.latest_recorded_at), now)}</ReadingTime>
                    </span>
                  </TableCell>
                  <TableCell className="tabular-nums">{m.count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

function YeastLine({ batch }: { batch: BatchDetail }) {
  // Optional in the generated type (the fields have defaults), though the API always sends them.
  const name = batch.yeast_name ?? null;
  const min = batch.yeast_min_temperature_c ?? null;
  const max = batch.yeast_max_temperature_c ?? null;
  if (min !== null && max !== null) {
    return (
      <p>
        Yeast: {name ?? "unnamed"} · {formatValue("temperature_c", min)} – {formatValue("temperature_c", max)}
      </p>
    );
  }
  if (name !== null) return <p>Yeast: {name} · no temperature range set</p>;
  return <p className="text-muted-foreground">No yeast set</p>;
}
