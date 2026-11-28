import Link from "next/link";

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { YeastStatusBadge } from "@/components/yeast-status";
import type { Batch, Device } from "@/lib/api/client";
import { formatAge } from "@/lib/time";
import { AMBIENT_CAVEAT, type YeastStatus } from "@/lib/yeast";

/** One row per batch, each linking to its batch page; `statuses` from `yeastStatuses`. */
export function BatchTable({
  batches,
  statuses,
  devices,
  showDevice,
  now,
}: {
  batches: readonly Batch[];
  statuses: ReadonlyMap<number, YeastStatus>;
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
            <TableHead>Yeast range</TableHead>
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
                    <span className="text-primary">Running</span>
                  ) : (
                    `Ended ${formatAge(new Date(b.ended_at), now)}`
                  )}
                </TableCell>
                <TableCell>
                  {status !== undefined && <YeastStatusBadge status={status} ambient={isAmbient(b.device_id)} />}
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
