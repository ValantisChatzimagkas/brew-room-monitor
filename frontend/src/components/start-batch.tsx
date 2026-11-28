import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import type { RunningBatch } from "@/lib/history";

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
