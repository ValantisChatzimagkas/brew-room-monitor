import type { YeastFit } from "@/lib/api/client";

type YeastSplitItem = { label: "below" | "inside" | "above"; count: number; flagged: boolean };

/** A batch's readings against its yeast range, in display order; any reading outside it is flagged. */
export function yeastSplit(fit: YeastFit): YeastSplitItem[] {
  return [
    { label: "below", count: fit.below, flagged: fit.below > 0 },
    { label: "inside", count: fit.inside, flagged: false },
    { label: "above", count: fit.above, flagged: fit.above > 0 },
  ];
}
