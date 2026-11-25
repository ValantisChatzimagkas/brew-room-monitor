import type { BatchDetail } from "@/lib/api/client";
import { formatValue } from "@/lib/metrics";
import { yeastSplit } from "@/lib/yeast";

/** The batch's yeast and, when it has a range, its readings below / inside / above it. */
export function BatchYeast({ batch }: { batch: BatchDetail }) {
  return (
    <div className="mb-4 text-sm">
      <YeastLine batch={batch} />
      {batch.yeast_fit !== null && (
        <p className="tabular-nums">
          {yeastSplit(batch.yeast_fit).map((item, i) => (
            <span key={item.label}>
              {i > 0 && " · "}
              <span className={item.flagged ? "font-medium text-out-of-range" : undefined}>
                {item.count} {item.label}
              </span>
            </span>
          ))}
        </p>
      )}
    </div>
  );
}

function YeastLine({ batch }: { batch: BatchDetail }) {
  // Optional in the generated type (the fields have defaults), though the API always sends them.
  const name = batch.yeast_name ?? null;
  const min = batch.yeast_min_temperature_c ?? null;
  const max = batch.yeast_max_temperature_c ?? null;
  if (min !== null && max !== null) {
    return (
      <p>
        Yeast: {name ?? "unnamed"} · {formatValue("temperature_c", min)} – {formatValue("temperature_c", max)}
      </p>
    );
  }
  if (name !== null) return <p>Yeast: {name} · no temperature range set</p>;
  return <p className="text-muted-foreground">No yeast set</p>;
}
