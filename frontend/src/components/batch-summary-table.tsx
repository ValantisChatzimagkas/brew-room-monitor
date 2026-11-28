import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { BatchDetail } from "@/lib/api/client";
import { formatValue, inMetricOrder, METRIC_INFO } from "@/lib/metrics";
import { formatAge } from "@/lib/time";

export function BatchSummaryTable({ metrics, now }: { metrics: BatchDetail["metrics"]; now: Date }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Metric</TableHead>
          <TableHead className="text-right">Min</TableHead>
          <TableHead className="text-right">Max</TableHead>
          <TableHead className="text-right">Average</TableHead>
          <TableHead className="text-right">Latest</TableHead>
          <TableHead className="text-right">Readings</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {inMetricOrder(metrics).map((m) => (
          <TableRow key={m.metric}>
            <TableCell>{METRIC_INFO[m.metric].label}</TableCell>
            <TableCell className="text-right tabular-nums">{formatValue(m.metric, m.min_value)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatValue(m.metric, m.max_value)}</TableCell>
            <TableCell className="text-right tabular-nums">{formatValue(m.metric, m.avg_value)}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatValue(m.metric, m.latest_value)}{" "}
              <span className="text-muted-foreground">
                {formatAge(new Date(m.latest_recorded_at), now)}
              </span>
            </TableCell>
            <TableCell className="text-right tabular-nums">{m.count}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
