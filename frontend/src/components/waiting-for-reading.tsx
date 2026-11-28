import { FIRMWARE_DOCS } from "@/lib/devices";

/** Empty state for a device that has never sent a reading: only flashing it fills it. */
export function WaitingForReading() {
  return (
    <p className="text-muted-foreground">
      Waiting for first reading.{" "}
      <a href={FIRMWARE_DOCS} target="_blank" rel="noopener noreferrer" className="underline">
        How to flash it
      </a>
      .
    </p>
  );
}
