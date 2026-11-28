import { isPartial, READINGS_LIMIT } from "@/lib/history";

export function PartialNotice({ count, where }: { count: number; where: string }) {
  if (!isPartial(count)) return null;
  return (
    <p className="mb-2 text-sm text-muted-foreground">
      Partial: showing only the newest {READINGS_LIMIT} readings {where}.
    </p>
  );
}
