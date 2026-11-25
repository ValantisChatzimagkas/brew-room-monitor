import type { TemperatureNote } from "@/lib/api/client";
import { AMBIENT_CAVEAT, NOTE_CAVEATS, noteText, type YeastRange } from "@/lib/yeast";

/** What the batch's temperature history may mean for the beer, with the caveats that keep it honest. */
export function BatchNotes({
  notes,
  range,
  ambient,
}: {
  notes: TemperatureNote[];
  range: YeastRange;
  ambient: boolean;
}) {
  if (notes.length === 0) return null;
  return (
    <section className="mb-4 text-sm">
      <h2 className="mb-2 font-medium">What the temperature may mean</h2>
      <ul className="mb-2 list-disc space-y-1 pl-5">
        {notes.map((note) => (
          <li key={note.code}>{noteText(note, range)}</li>
        ))}
      </ul>
      <div className="text-muted-foreground">
        {ambient && <p>{AMBIENT_CAVEAT}</p>}
        {NOTE_CAVEATS.map((caveat) => (
          <p key={caveat}>{caveat}</p>
        ))}
      </div>
    </section>
  );
}
