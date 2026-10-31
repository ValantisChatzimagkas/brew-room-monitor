import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { MetricChart } from "@/components/metric-chart";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getApi } from "@/lib/api/client";
import { parseDeviceId, parseRange, RANGES, rangeSince, READINGS_LIMIT, toPoints } from "@/lib/history";
import { METRIC_INFO, METRIC_ORDER } from "@/lib/metrics";

export default function DevicePage({ params, searchParams }: PageProps<"/devices/[id]">) {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Link href="/" className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← Dashboard
      </Link>
      <Suspense fallback={<p className="text-muted-foreground">Loading readings…</p>}>
        <DeviceDetail params={params} searchParams={searchParams} />
      </Suspense>
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
                <MetricChart metric={metric} points={toPoints(rows)} from={since.getTime()} to={now.getTime()} />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
