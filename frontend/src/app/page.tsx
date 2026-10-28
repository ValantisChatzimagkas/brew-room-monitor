import { Suspense } from "react";

import { getApi, type Device, type Metric, type Reading } from "@/lib/api/client";

const METRIC_LABEL: Record<Metric, string> = {
  temperature_c: "Temperature (°C)",
  humidity_pct: "Humidity (%)",
  pressure_hpa: "Pressure (hPa)",
  specific_gravity: "Gravity (SG)",
  battery_v: "Battery (V)",
};

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-semibold">Brew Room Monitor</h1>
      <Suspense fallback={<p className="text-zinc-500">Loading sensors…</p>}>
        <DeviceList />
      </Suspense>
    </main>
  );
}

async function DeviceList() {
  const api = await getApi();
  const [devices, readings] = await Promise.all([
    api.GET("/api/v1/devices"),
    api.GET("/api/v1/readings", { params: { query: { limit: 500 } } }),
  ]);
  if (devices.error || readings.error) throw new Error("Failed to load data from the API");

  if (devices.data.length === 0) {
    return <p className="text-zinc-500">No devices yet. Register one via POST /api/v1/devices.</p>;
  }

  return (
    <ul className="grid gap-4 sm:grid-cols-2">
      {devices.data.map((device) => (
        <DeviceCard key={device.id} device={device} latest={latestByMetric(readings.data, device.id)} />
      ))}
    </ul>
  );
}

function DeviceCard({ device, latest }: { device: Device; latest: Reading[] }) {
  return (
    <li className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <h2 className="font-medium">{device.name}</h2>
      <p className="mb-3 text-sm text-zinc-500">
        {device.kind} {device.location && `· ${device.location}`}
      </p>
      {latest.length === 0 ? (
        <p className="text-sm text-zinc-500">No readings yet</p>
      ) : (
        <dl className="grid grid-cols-2 gap-1 text-sm">
          {latest.map((r) => (
            <div key={r.metric} className="contents">
              <dt className="text-zinc-500">{METRIC_LABEL[r.metric]}</dt>
              <dd className="tabular-nums">{r.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

/** Readings arrive newest first, so the first one seen per metric is the latest. */
function latestByMetric(readings: Reading[], deviceId: number): Reading[] {
  const latest = new Map<Metric, Reading>();
  for (const r of readings) {
    if (r.device_id === deviceId && !latest.has(r.metric)) latest.set(r.metric, r);
  }
  return [...latest.values()];
}
