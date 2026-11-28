import Link from "next/link";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/auto-refresh";
import { LocalDateTime } from "@/components/local-date-time";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { WaitingForReading } from "@/components/waiting-for-reading";
import { getApi, type Device, type Reading } from "@/lib/api/client";
import { DEVICE_KIND_LABEL } from "@/lib/devices";
import { formatValue, METRIC_INFO, METRIC_ORDER } from "@/lib/metrics";
import { groupByRoom } from "@/lib/rooms";
import { deviceStatus } from "@/lib/status";
import { formatAge } from "@/lib/time";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Brew Room Monitor</h1>
        <Link href="/devices/new" className={buttonVariants({ variant: "outline" })}>
          Register a device
        </Link>
      </div>
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
    return (
      <p className="text-muted-foreground">
        No devices yet.{" "}
        <Link href="/devices/new" className="underline">
          Register your first device
        </Link>
        .
      </p>
    );
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
  const status = deviceStatus(device, latest, now);
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
            {status === "stale" && <span className="text-sm font-normal text-stale">Stale</span>}
            {device.revoked_at && (
              <span className="text-sm font-normal text-muted-foreground">
                Revoked <LocalDateTime iso={device.revoked_at} />
              </span>
            )}
          </CardTitle>
          <CardDescription>{DEVICE_KIND_LABEL[device.kind]}</CardDescription>
        </CardHeader>
        <CardContent>
          {status === "waiting" ? (
            <WaitingForReading />
          ) : latest.length === 0 ? (
            <p className="text-sm text-muted-foreground">No readings yet</p>
          ) : (
            <dl className="grid grid-cols-3 gap-x-3 gap-y-1 text-sm">
              {latest.map((r) => (
                <div key={r.metric} className="contents">
                  <dt className="text-muted-foreground">{METRIC_INFO[r.metric].label}</dt>
                  <dd className="tabular-nums">{formatValue(r.metric, r.value)}</dd>
                  <dd className={status === "stale" ? "text-stale" : "text-muted-foreground"}>
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
