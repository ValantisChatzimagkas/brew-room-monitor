"use client";

import { type FormEvent, startTransition, useActionState, useState } from "react";

import { endBatch } from "@/app/batches/[id]/actions";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { localInputToUtc, toLocalInput } from "@/lib/time";

/** "End batch" button that opens an inline form for the end time, entered in the browser's local time. */
export function EndBatchForm({ batchId }: { batchId: number }) {
  const [initial, setInitial] = useState<string | null>(null);
  if (initial === null) {
    // "Now" is read on click, not at render, so server and browser HTML agree.
    return <Button onClick={() => setInitial(toLocalInput(new Date()))}>End batch</Button>;
  }
  return <OpenForm batchId={batchId} initial={initial} onClose={() => setInitial(null)} />;
}

/** Mounted only while open, so closing drops the typed value and any error. */
function OpenForm({ batchId, initial, onClose }: { batchId: number; initial: string; onClose: () => void }) {
  const [value, setValue] = useState(initial);
  const [inputError, setInputError] = useState<string | null>(null);
  const [state, formAction, pending] = useActionState(endBatch.bind(null, batchId), { error: null });
  const error = inputError ?? state.error;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const utc = localInputToUtc(value);
    setInputError(utc === null ? "Enter a valid end time." : null);
    if (utc !== null) startTransition(() => formAction(utc));
  }

  return (
    <form onSubmit={submit} className="flex max-w-xs flex-col gap-3">
      <Field data-invalid={error !== null || undefined}>
        <FieldLabel htmlFor="end-time">End time</FieldLabel>
        <Input
          id="end-time"
          type="datetime-local"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          aria-invalid={error !== null || undefined}
        />
        <FieldError>{error}</FieldError>
      </Field>
      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          End batch
        </Button>
        <Button type="button" variant="outline" onClick={onClose}>
          Keep running
        </Button>
      </div>
    </form>
  );
}
