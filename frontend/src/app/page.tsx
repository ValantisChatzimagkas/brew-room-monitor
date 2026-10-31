import Link from "next/link";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { ReadingTime } from "@/components/reading-time";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getApi, type Device, type Reading } from "@/lib/api/client";
import { formatValue, METRIC_INFO, METRIC_ORDER } from "@/lib/metrics";
import { groupByRoom } from "@/lib/rooms";
import { formatAge, isStale } from "@/lib/time";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-semibold">Brew Room Monitor</h1>
      <Suspense fallback={<p className="text-muted-foreground">Loading sensors…</p>}>
        <DeviceList />
      </Suspense>
      <AutoRefresh />
    </main>
  );
}

async function DeviceList() {
  const api = await getApi();
  const now = new Date();
  const devices = await api.GET("/api/v1/devices");
  if (devices.error) throw new Error("Failed to load data from the API");

  if (devices.data.length === 0) {
    return <p className="text-muted-foreground">No devices yet. Register one via POST /api/v1/devices.</p>;
  }

  // Newest reading per device and metric: a quiet device must not fall out of a global "newest N" window.
  const latestPerDevice = await Promise.all(
    devices.data.map(async (device) => {
      const results = await Promise.all(
        METRIC_ORDER.map((metric) =>
          api.GET("/api/v1/readings", { params: { query: { device_id: device.id, metric, limit: 1 } } }),
        ),
      );
      const latest: Reading[] = [];
      for (const result of results) {
        if (result.error) throw new Error("Failed to load data from the API");
        if (result.data[0]) latest.push(result.data[0]);
      }
      return latest;
    }),
  );

  const entries = devices.data.map((device, i) => ({ device, latest: latestPerDevice[i], location: device.location }));

  return (
    <div className="grid gap-8">
      {groupByRoom(entries).map((group) => (
        <section key={group.room ?? "no-room"}>
          <h2 className="mb-3 text-lg font-medium">{group.room ?? "No room"}</h2>
          <ul className="grid gap-4 sm:grid-cols-2">
            {group.items.map(({ device, latest }) => (
              <DeviceCard key={device.id} device={device} latest={latest} now={now} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function DeviceCard({ device, latest, now }: { device: Device; latest: Reading[]; now: Date }) {
  const stale = isStale(latest, now);
  return (
    <li>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2">
            <h3>
              <Link href={`/devices/${device.id}`} className="hover:underline">
                {device.name}
              </Link>
            </h3>
            {stale && <span className="text-sm font-normal text-stale">Stale</span>}
          </CardTitle>
          <CardDescription>
            {device.kind}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {latest.length === 0 ? (
            <p className="text-sm text-muted-foreground">No readings yet</p>
          ) : (
            <dl className="grid grid-cols-3 gap-x-3 gap-y-1 text-sm">
              {latest.map((r) => (
                <div key={r.metric} className="contents">
                  <dt className="text-muted-foreground">{METRIC_INFO[r.metric].label}</dt>
                  <dd className="tabular-nums">{formatValue(r.metric, r.value)}</dd>
                  <dd className={stale ? "text-stale" : "text-muted-foreground"}>
                    <ReadingTime iso={r.recorded_at}>{formatAge(new Date(r.recorded_at), now)}</ReadingTime>
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </CardContent>
      </Card>
    </li>
  );
}
