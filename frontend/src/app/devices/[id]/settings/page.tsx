import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { EditDeviceForm } from "@/components/edit-device-form";
import { LocalDateTime } from "@/components/local-date-time";
import { RekeyDeviceForm } from "@/components/rekey-device-form";
import { RevokeDeviceForm } from "@/components/revoke-device-form";
import type { Room } from "@/components/room-field";
import { findDevice, getApi } from "@/lib/api/client";
import { NEW_ROOM } from "@/lib/devices";
import { parseId } from "@/lib/history";

export default function DeviceSettingsPage({ params }: PageProps<"/devices/[id]/settings">) {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
        <DeviceSettings params={params} />
      </Suspense>
    </main>
  );
}

async function DeviceSettings({ params }: Pick<PageProps<"/devices/[id]/settings">, "params">) {
  const { id: rawId } = await params;
  const id = parseId(rawId);
  if (id === null) notFound();

  const api = await getApi();
  const device = await findDevice(id);
  if (!device) notFound();
  let rooms: Room[] = [];
  // Only an ambient device's room is editable, so an in_vessel one gets no room list.
  if (device.kind === "ambient") {
    const locations = await api.GET("/api/v1/locations", { params: { query: { limit: 500 } } });
    if (locations.error) throw new Error("Failed to load data from the API");
    rooms = locations.data.map(({ id, name }) => ({ id, name }));
  }
  // A legacy ambient device without a room starts on the first room: saving needs one.
  const initialId = device.location?.id ?? rooms[0]?.id;
  const initialRoom = initialId === undefined ? NEW_ROOM : String(initialId);

  return (
    <>
      <Link href={`/devices/${id}`} className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← {device.name}
      </Link>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Settings</h1>
        {device.revoked_at !== null && (
          <span className="text-muted-foreground">
            Revoked <LocalDateTime iso={device.revoked_at} />
          </span>
        )}
      </header>
      <div className="grid gap-8">
        <section>
          <h2 className="mb-3 text-lg font-medium">Name and room</h2>
          <EditDeviceForm
            deviceId={id}
            kind={device.kind}
            initialName={device.name}
            initialRoom={initialRoom}
            rooms={rooms}
          />
        </section>
        <section>
          <h2 className="mb-3 text-lg font-medium">Token</h2>
          <p className="mb-3 text-sm text-muted-foreground">Re-key a device whose token was lost or that you reflash.</p>
          {/* Always rendered: the refresh() after a re-key clears `revoked_at`, and remounting this form would
              drop the new token on screen. */}
          <RekeyDeviceForm deviceId={id} deviceName={device.name} />
        </section>
        {device.revoked_at === null && (
          <section>
            <h2 className="mb-3 text-lg font-medium">Revoke</h2>
            <RevokeDeviceForm deviceId={id} deviceName={device.name} />
          </section>
        )}
      </div>
    </>
  );
}
