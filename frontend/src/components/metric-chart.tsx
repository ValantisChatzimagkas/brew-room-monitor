"use client";

import { CartesianGrid, Dot, Line, LineChart, ReferenceArea, XAxis, YAxis } from "recharts";

import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { Metric } from "@/lib/api/client";
import type { ChartPoint } from "@/lib/history";
import { formatValue, METRIC_INFO } from "@/lib/metrics";
import { chartTickFormat } from "@/lib/time";
import { yeastPosition, type YeastRange } from "@/lib/yeast";

const MARKER_SIZE = 5;
const OUT_OF_RANGE_LABEL = { above: "Above yeast range", below: "Below yeast range" } as const;

/** Times are formatted here, in the browser, so the server's timezone never reaches the HTML. */
export function MetricChart({
  metric,
  points,
  from,
  to,
  yeastRange,
}: {
  metric: Metric;
  points: ChartPoint[];
  from: number;
  to: number;
  yeastRange?: YeastRange;
}) {
  const { label, decimals } = METRIC_INFO[metric];
  const config: ChartConfig = { value: { label, color: "var(--primary)" } };
  const position = (value: number) => (yeastRange ? yeastPosition(value, yeastRange) : "inside");

  return (
    <>
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
          {yeastRange && (
            // extendDomain: the whole band stays visible even when every reading sits inside it.
            <ReferenceArea
              y1={yeastRange.min}
              y2={yeastRange.max}
              ifOverflow="extendDomain"
              fill="var(--color-yeast-range)"
            />
          )}
          <ChartTooltip
            content={
              <ChartTooltipContent
                indicator="line"
                labelFormatter={(_, payload) => {
                  const time: unknown = payload[0]?.payload?.time;
                  return typeof time === "number" ? new Date(time).toLocaleString() : null;
                }}
                formatter={(value) => {
                  if (typeof value !== "number") return String(value);
                  const where = position(value);
                  return (
                    <span>
                      {formatValue(metric, value)}
                      {where !== "inside" && <span className="text-out-of-range"> · {OUT_OF_RANGE_LABEL[where]}</span>}
                    </span>
                  );
                }}
              />
            }
          />
          <Line
            dataKey="value"
            name={label}
            type="monotone"
            stroke="var(--color-value)"
            strokeWidth={2}
            dot={({ cx, cy, r, fill, stroke, strokeWidth, value }) => {
              if (cx === undefined || cy === undefined || typeof value !== "number") return null;
              const where = position(value);
              if (where !== "inside") {
                // A shape, not only a colour, marks the reading: ▲ above the range, ▼ below it.
                const tip = where === "above" ? cy - MARKER_SIZE : cy + MARKER_SIZE;
                const base = where === "above" ? cy + MARKER_SIZE : cy - MARKER_SIZE;
                return (
                  <path
                    d={`M ${cx} ${tip} L ${cx + MARKER_SIZE} ${base} L ${cx - MARKER_SIZE} ${base} Z`}
                    fill="var(--color-out-of-range)"
                  />
                );
              }
              if (points.length !== 1) return null;
              return <Dot cx={cx} cy={cy} r={r} fill={fill} stroke={stroke} strokeWidth={strokeWidth} />;
            }}
            isAnimationActive={false}
          />
        </LineChart>
      </ChartContainer>
      {yeastRange && (
        <p className="mt-2 text-sm text-muted-foreground">
          <span className="text-out-of-range">▲</span> above range · <span className="text-out-of-range">▼</span> below
          range · Shaded: yeast range
        </p>
      )}
    </>
  );
}
