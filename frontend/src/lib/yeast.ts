import type { BatchDetail, TemperatureNote, YeastFit } from "@/lib/api/client";
import { formatValue } from "./metrics";
import { formatDuration } from "./time";

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

/**
 * The brewer-facing wording of a backend temperature note. Fault notes say "may": possibilities, not a
 * diagnosis. No threshold or day number is written here; the numbers come from the note itself.
 */
export function noteText(note: TemperatureNote, range: YeastRange): string {
  const duration = formatDuration(note.duration_s);
  const temp = (value: number) => formatValue("temperature_c", value);
  switch (note.code) {
    case "early_hot":
      return `${duration} at ${temp(range.max + requireDelta(note))} or more early in fermentation, well above the yeast's range. The beer may have strong fruity esters and "hot", solvent-like fusel alcohols; these don't fade with conditioning.`;
    case "early_warm":
      return `${duration} above ${temp(range.max)} early in fermentation. The beer may taste fruitier than intended, possibly a little "hot" (fusel alcohols); these don't fade with conditioning.`;
    case "late_cold":
      return `${duration} below ${temp(range.min)} later in fermentation. It may finish slowly or stall and leave diacetyl (a buttery note); a warm rest near the end helps.`;
    case "sharp_drop":
      return `The temperature dropped ${temp(requireDelta(note))} within ${duration}. Unless you cooled it on purpose, the yeast may go dormant: check that gravity is still falling.`;
    case "late_warm":
      return `${duration} above ${temp(range.max)} late in fermentation. Not a fault: late warmth may help the yeast clean up diacetyl.`;
    case "in_range":
      // Not "the whole time": a reading's span is capped, so a sensor gap is not covered.
      return `Every reading stayed within ${temp(range.min)} – ${temp(range.max)}.`;
    default: {
      const unknown: never = note.code;
      throw new Error(`Unknown temperature note: ${String(unknown)}`);
    }
  }
}

// The backend always sets delta_c on these codes; a null is a broken contract, not a number to make up.
function requireDelta(note: TemperatureNote): number {
  if (note.delta_c === null) throw new Error(`Temperature note ${note.code} is missing delta_c`);
  return note.delta_c;
}

export const NOTE_CAVEATS: readonly string[] = [
  "These are possibilities, not a diagnosis.",
  "Modest temperature differences often aren't detectable in blind tastings.",
  "Pitch rate, oxygen and yeast strain matter too.",
  "Gravity, not temperature, shows whether fermentation has finished.",
];

export const AMBIENT_CAVEAT =
  "These are room readings: the wort usually runs 2–5 °C warmer than the room in the first days.";
