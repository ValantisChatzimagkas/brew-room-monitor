"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Metric } from "@/lib/api/client";
import type { ChartPoint } from "@/lib/history";
import { formatValue, METRIC_INFO } from "@/lib/metrics";
import { chartTickFormat } from "@/lib/time";

/** Times are formatted here, in the browser, so the server's timezone never reaches the HTML. */
export function MetricChart({
  metric,
  points,
  from,
  to,
}: {
  metric: Metric;
  points: ChartPoint[];
  from: number;
  to: number;
}) {
  const { label, decimals } = METRIC_INFO[metric];
  const config: ChartConfig = { value: { label, color: "var(--primary)" } };

  return (
    <ChartContainer config={config} className="aspect-auto h-64 w-full">
      <LineChart data={points} margin={{ left: 8, right: 8 }}>
        <CartesianGrid vertical={false} />
        <XAxis
          dataKey="time"
          type="number"
          scale="time"
          domain={[from, to]}
          tickFormatter={(t: number) => new Date(t).toLocaleString([], chartTickFormat(to - from))}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          domain={["auto", "auto"]}
          tickFormatter={(v: number) => v.toFixed(decimals)}
          tickLine={false}
          axisLine={false}
          width={48}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              indicator="line"
              labelFormatter={(_, payload) => {
                const time: unknown = payload[0]?.payload?.time;
                return typeof time === "number" ? new Date(time).toLocaleString() : null;
              }}
              formatter={(value) => (typeof value === "number" ? formatValue(metric, value) : String(value))}
            />
          }
        />
        <Line
          dataKey="value"
          name={label}
          type="monotone"
          stroke="var(--color-value)"
          strokeWidth={2}
          dot={points.length === 1}
          isAnimationActive={false}
        />
      </LineChart>
    </ChartContainer>
  );
}
