import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

type RunningBatch = { id: number; name: string; deviceName: string };

/**
 * The running batches that keep a device from starting one. A revoked device can't start a batch even once
 * its batch ends, so its running batch isn't offered.
 */
export function runningBatches(
  devices: readonly { id: number; name: string; revoked_at: string | null }[],
  batches: readonly { id: number; name: string; device_id: number; ended_at: string | null }[],
): RunningBatch[] {
  const devicesById = new Map(devices.map((d) => [d.id, d]));
  return batches.flatMap((b) => {
    const device = devicesById.get(b.device_id);
    if (b.ended_at !== null || device === undefined || device.revoked_at !== null) return [];
    return [{ id: b.id, name: b.name, deviceName: device.name }];
  });
}

/** "Start batch": straight to the form when one device can start a batch, via the chooser when several can. */
export function StartBatchLink({
  startable,
  running,
}: {
  startable: { id: number; name: string }[];
  running: RunningBatch[];
}) {
  if (startable.length === 0) return <CannotStartBatch running={running} />;
  const href = startable.length === 1 ? `/devices/${startable[0].id}/batches/new` : "/batches/new";
  return (
    <Link href={href} className={buttonVariants()}>
      Start batch
    </Link>
  );
}

/** Why no device can start a batch, with the link that changes that. */
export function CannotStartBatch({ running }: { running: RunningBatch[] }) {
  if (running.length === 0) {
    return (
      <p className="text-muted-foreground">
        No device can start a batch.{" "}
        <Link href="/devices/new" className="underline">
          Register a device
        </Link>
        .
      </p>
    );
  }
  return (
    <ul className="grid gap-1 text-muted-foreground">
      {running.map((b) => (
        <li key={b.id}>
          <Link href={`/batches/${b.id}`} className="underline">
            {b.name}
          </Link>{" "}
          is running on {b.deviceName}. End it to start another.
        </li>
      ))}
    </ul>
  );
}
