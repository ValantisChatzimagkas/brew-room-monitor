import type { BatchDetail, YeastFit } from "@/lib/api/client";

type YeastSplitItem = { label: "below" | "inside" | "above"; count: number; flagged: boolean };

/** A batch's readings against its yeast range, in display order; any reading outside it is flagged. */
export function yeastSplit(fit: YeastFit): YeastSplitItem[] {
  return [
    { label: "below", count: fit.below, flagged: fit.below > 0 },
    { label: "inside", count: fit.inside, flagged: false },
    { label: "above", count: fit.above, flagged: fit.above > 0 },
  ];
}

export type YeastRange = { min: number; max: number };

export function yeastRange(
  batch: Pick<BatchDetail, "yeast_min_temperature_c" | "yeast_max_temperature_c">,
): YeastRange | null {
  // Optional in the generated type (the fields have defaults), though the API always sends them.
  const min = batch.yeast_min_temperature_c ?? null;
  const max = batch.yeast_max_temperature_c ?? null;
  return min !== null && max !== null ? { min, max } : null;
}

/** Bounds count as inside, as in the backend's `yeast_fit`. */
export function yeastPosition(value: number, range: YeastRange): "below" | "inside" | "above" {
  if (value < range.min) return "below";
  if (value > range.max) return "above";
  return "inside";
}
