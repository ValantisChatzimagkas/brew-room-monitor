import Link from "next/link";
import { Suspense } from "react";

import { RegisterDeviceForm } from "@/components/register-device-form";
import { getApi } from "@/lib/api/client";

export default function NewDevicePage() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <Link href="/" className="mb-4 inline-block text-sm text-muted-foreground hover:underline">
        ← Dashboard
      </Link>
      <h1 className="mb-6 text-2xl font-semibold">Register a device</h1>
      <Suspense fallback={<p className="text-muted-foreground">Loading…</p>}>
        <NewDevice />
      </Suspense>
    </main>
  );
}

async function NewDevice() {
  const api = await getApi();
  const locations = await api.GET("/api/v1/locations", { params: { query: { limit: 500 } } });
  if (locations.error) throw new Error("Failed to load data from the API");
  return <RegisterDeviceForm rooms={locations.data.map(({ id, name }) => ({ id, name }))} />;
}
