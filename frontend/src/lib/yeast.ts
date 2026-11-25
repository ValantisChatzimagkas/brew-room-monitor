import type { BatchDetail, YeastFit } from "@/lib/api/client";

type YeastSplitItem = { label: "below" | "inside" | "above"; seconds: number; flagged: boolean };

/** Time a batch's readings spent against its yeast range, in display order; any time outside it is flagged. */
export function yeastSplit(fit: YeastFit): YeastSplitItem[] {
  return [
    { label: "below", seconds: fit.below_s, flagged: fit.below_s > 0 },
    { label: "inside", seconds: fit.inside_s, flagged: false },
    { label: "above", seconds: fit.above_s, flagged: fit.above_s > 0 },
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
