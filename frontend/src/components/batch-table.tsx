import Link from "next/link";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { YeastStatusBadge } from "@/components/yeast-status";
import type { Batch, BatchYeastStatus, Device } from "@/lib/api/client";
import { formatAge } from "@/lib/time";
import { AMBIENT_CAVEAT } from "@/lib/yeast";

/** One row per batch, each linking to its batch page; `statuses` from `yeastStatuses`. */
export function BatchTable({
  batches,
  statuses,
  devices,
  showDevice,
  now,
}: {
  batches: readonly Batch[];
  statuses: ReadonlyMap<number, BatchYeastStatus>;
  devices: ReadonlyMap<number, Pick<Device, "name" | "kind">>;
  showDevice: boolean;
  now: Date;
}) {
  const isAmbient = (deviceId: number) => devices.get(deviceId)?.kind === "ambient";
  const anyAmbientStatus = batches.some((b) => statuses.has(b.id) && isAmbient(b.device_id));

  return (
    <>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Batch</TableHead>
            {showDevice && <TableHead>Device</TableHead>}
            <TableHead>Started</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Yeast</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {batches.map((b) => {
            const status = statuses.get(b.id);
            return (
              <TableRow key={b.id}>
                <TableCell>
                  <Link href={`/batches/${b.id}`} className="hover:underline">
                    {b.name}
                  </Link>
                </TableCell>
                {showDevice && <TableCell>{devices.get(b.device_id)?.name ?? `Device ${b.device_id}`}</TableCell>}
                <TableCell>
                  {formatAge(new Date(b.started_at), now)}
                </TableCell>
                <TableCell>
                  {b.ended_at === null ? (
                    "Running"
                  ) : (
                    `Ended ${formatAge(new Date(b.ended_at), now)}`
                  )}
                </TableCell>
                <TableCell>
                  {status !== undefined && (
                    <YeastStatusBadge
                      status={status.status}
                      lastReadingAt={status.lastReadingAt}
                      ambient={isAmbient(b.device_id)}
                      now={now}
                    />
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {anyAmbientStatus && <p className="mt-2 text-sm text-muted-foreground">{AMBIENT_CAVEAT}</p>}
    </>
  );
}
