import { noRecentDataText } from "@/lib/status";
import { YEAST_STATUS_LABEL, type YeastStatus } from "@/lib/yeast";

const STATUS_CLASS: Record<YeastStatus, string | undefined> = {
  in_range: undefined,
  too_warm: "font-medium text-out-of-range",
  too_cold: "font-medium text-out-of-range",
  no_recent_data: "font-medium text-stale",
};

/**
 * A running batch's yeast status as a word (colour only reinforces it), marked when it comes from room readings.
 * No recent data also says since when, from `lastReadingAt`, the batch's newest temperature reading.
 */
export function YeastStatusBadge({
  status,
  lastReadingAt,
  ambient,
  now,
}: {
  status: YeastStatus;
  lastReadingAt: string | null;
  ambient: boolean;
  now: Date;
}) {
  const word =
    status === "no_recent_data"
      ? noRecentDataText(lastReadingAt === null ? [] : [{ recorded_at: lastReadingAt }], now)
      : YEAST_STATUS_LABEL[status];
  return (
    <span>
      <span className={STATUS_CLASS[status]}>{word}</span>
      {ambient && <span className="text-muted-foreground"> · room</span>}
    </span>
  );
}
