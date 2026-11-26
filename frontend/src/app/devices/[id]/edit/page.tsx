import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { EditDeviceForm } from "@/components/edit-device-form";
import { findDevice, getApi } from "@/lib/api/client";
import { NEW_ROOM } from "@/lib/devices";
import { parseId } from "@/lib/history";

export default function EditDevicePage({ params }: PageProps<"/devices/[id]/edit">) {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
        <EditDevice params={params} />
      </Suspense>
    </main>
  );
}

async function EditDevice({ params }: Pick<PageProps<"/devices/[id]/edit">, "params">) {
  const { id: rawId } = await params;
  const id = parseId(rawId);
  if (id === null) notFound();

  const api = await getApi();
  const device = await findDevice(id);
  if (!device) notFound();
  const locations = await api.GET("/api/v1/locations", { params: { query: { limit: 500 } } });
  if (locations.error) throw new Error("Failed to load data from the API");
  const rooms = locations.data.map(({ id, name }) => ({ id, name }));
  // A legacy ambient device without a room starts on the first room: saving needs one.
  const initialId = device.location?.id ?? rooms[0]?.id;
  const initialRoom = initialId === undefined ? NEW_ROOM : String(initialId);

  return (
    <>
      <Link href={`/devices/${id}`} className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← {device.name}
      </Link>
      <h1 className="mb-6 text-2xl font-semibold">Edit device</h1>
      <EditDeviceForm
        deviceId={id}
        kind={device.kind}
        initialName={device.name}
        initialRoom={initialRoom}
        rooms={rooms}
      />
    </>
  );
}
