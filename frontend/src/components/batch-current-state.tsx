import type { ReactNode } from "react";

import { ReadingTime } from "@/components/reading-time";
import { YeastStatusBadge } from "@/components/yeast-status";
import { formatValue } from "@/lib/metrics";
import { formatAge } from "@/lib/time";
import { formatYeastRange, type YeastRange, type YeastStatus } from "@/lib/yeast";

/**
 * How a running batch is doing now, on one line: its yeast status, newest temperature beside the yeast
 * range, and how old that reading is. A stale reading still shows, after "No recent data", with its age.
 */
export function BatchCurrentState({
  status,
  temperature,
  range,
  ambient,
  now,
}: {
  status: YeastStatus | null;
  temperature: { value: number; recordedAt: string } | null;
  range: YeastRange | null;
  ambient: boolean;
  now: Date;
}) {
  const parts: { key: string; node: ReactNode }[] = [];
  if (status !== null) parts.push({ key: "status", node: <YeastStatusBadge status={status} ambient={ambient} /> });
  parts.push(
    temperature === null
      ? { key: "temperature", node: <span className="text-muted-foreground">No temperature reading yet</span> }
      : {
          key: "temperature",
          node: <span className="font-medium tabular-nums">{formatValue("temperature_c", temperature.value)}</span>,
        },
  );
  if (range !== null) parts.push({ key: "range", node: `range ${formatYeastRange(range)}` });
  if (temperature !== null) {
    parts.push({
      key: "age",
      node: (
        <ReadingTime iso={temperature.recordedAt}>{formatAge(new Date(temperature.recordedAt), now)}</ReadingTime>
      ),
    });
  }

  return (
    <p className="tabular-nums">
      {parts.map(({ key, node }, i) => (
        <span key={key}>
          {i > 0 && " · "}
          {node}
        </span>
      ))}
    </p>
  );
}
