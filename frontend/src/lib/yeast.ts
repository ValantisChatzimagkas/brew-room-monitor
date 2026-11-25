import type { YeastFit } from "@/lib/api/client";

type YeastSplitItem = { label: "below" | "inside" | "above"; seconds: number; flagged: boolean };

/** Time a batch's readings spent against its yeast range, in display order; any time outside it is flagged. */
export function yeastSplit(fit: YeastFit): YeastSplitItem[] {
  return [
    { label: "below", seconds: fit.below_s, flagged: fit.below_s > 0 },
    { label: "inside", seconds: fit.inside_s, flagged: false },
    { label: "above", seconds: fit.above_s, flagged: fit.above_s > 0 },
  ];
}
