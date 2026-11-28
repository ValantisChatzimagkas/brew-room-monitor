import type { BatchDetail } from "@/lib/api/client";
import { formatDuration } from "@/lib/time";
import { formatYeastRange, yeastRange, yeastSplit } from "@/lib/yeast";

/** The batch's yeast and, when it has a range, the time its readings spent below / inside / above it. */
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
                {formatDuration(item.seconds)} {item.label}
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
  const range = yeastRange(batch);
  if (range !== null) {
    return (
      <p>
        Yeast: {name ?? "unnamed"} · {formatYeastRange(range)}
      </p>
    );
  }
  if (name !== null) return <p>Yeast: {name} · no temperature range set</p>;
  return <p className="text-muted-foreground">No yeast set</p>;
}
