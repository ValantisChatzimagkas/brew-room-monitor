import { Suspense } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getApi, type Device, type Reading } from "@/lib/api/client";
import { formatValue, METRIC_INFO, METRIC_ORDER } from "@/lib/metrics";
import { formatAge, isStale } from "@/lib/time";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-semibold">Brew Room Monitor</h1>
      <Suspense fallback={<p className="text-muted-foreground">Loading sensors…</p>}>
        <DeviceList />
      </Suspense>
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

  return (
    <ul className="grid gap-4 sm:grid-cols-2">
      {devices.data.map((device, i) => (
        <DeviceCard key={device.id} device={device} latest={latestPerDevice[i]} now={now} />
      ))}
    </ul>
  );
}

function DeviceCard({ device, latest, now }: { device: Device; latest: Reading[]; now: Date }) {
  const stale = isStale(latest, now);
  return (
    <li>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2">
            <h2>{device.name}</h2>
            {stale && <span className="text-sm font-normal text-stale">Stale</span>}
          </CardTitle>
          <CardDescription>
            {device.kind} {device.location && `· ${device.location.name}`}
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
                    {formatAge(new Date(r.recorded_at), now)}
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
