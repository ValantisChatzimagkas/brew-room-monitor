import { YEAST_STATUS_LABEL, type YeastStatus } from "@/lib/yeast";

const STATUS_CLASS: Record<YeastStatus, string | undefined> = {
  in_range: undefined,
  too_warm: "font-medium text-out-of-range",
  too_cold: "font-medium text-out-of-range",
  no_recent_data: "text-muted-foreground",
};

/** A running batch's yeast status as a word (colour only reinforces it), marked when it comes from room readings. */
export function YeastStatusBadge({ status, ambient }: { status: YeastStatus; ambient: boolean }) {
  return (
    <span>
      <span className={STATUS_CLASS[status]}>{YEAST_STATUS_LABEL[status]}</span>
      {ambient && <span className="text-muted-foreground"> · room</span>}
    </span>
  );
}
