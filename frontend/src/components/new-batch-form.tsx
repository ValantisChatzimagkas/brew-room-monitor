"use client";

import Link from "next/link";
import { type FormEvent, startTransition, useActionState, useState, useSyncExternalStore } from "react";

import { editBatch } from "@/app/batches/[id]/edit/actions";
import { startBatch } from "@/app/devices/[id]/batches/new/actions";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { localInputToUtc, toLocalInput } from "@/lib/time";

const subscribe = () => () => {};

/** A stored batch's editable fields; `startedAt` is UTC ISO, the others are input values. */
export type EditableBatch = {
  id: number;
  name: string;
  startedAt: string;
  yeastName: string;
  yeastMin: string;
  yeastMax: string;
};
type Props = { deviceId: number } | { batch: EditableBatch };

/**
 * Form for a new batch on a device, its start time defaulting to now, or, given `batch`, for editing that
 * batch. Times are in the browser's local time.
 */
export function NewBatchForm(props: Props) {
  // The server's time zone isn't the user's, so the fields (and "now") render only after hydration.
  const hydrated = useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
  if (!hydrated) return <p className="text-muted-foreground">Loading form…</p>;
  return <HydratedForm {...props} />;
}

function HydratedForm(props: Props) {
  const batch = "batch" in props ? props.batch : null;
  const [name, setName] = useState(batch?.name ?? "");
  const [start, setStart] = useState(() => toLocalInput(batch ? new Date(batch.startedAt) : new Date()));
  const [yeastName, setYeastName] = useState(batch?.yeastName ?? "");
  const [yeastMin, setYeastMin] = useState(batch?.yeastMin ?? "");
  const [yeastMax, setYeastMax] = useState(batch?.yeastMax ?? "");
  const [startError, setStartError] = useState<string | null>(null);
  const action = "batch" in props ? editBatch.bind(null, props.batch.id) : startBatch.bind(null, props.deviceId);
  const [state, formAction, pending] = useActionState(action, { errors: {}, conflict: null });
  const { errors, conflict } = state;
  const startReason = startError ?? errors.startedAt;
  const ended = conflict !== null && conflict.endedAt !== null ? conflict.endedAt : null;
  const conflictLink = conflict && (
    <Link href={`/batches/${conflict.id}`} className="underline">
      {conflict.name}
    </Link>
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const utc = localInputToUtc(start);
    setStartError(utc === null ? "Enter a valid start time." : null);
    if (utc !== null) startTransition(() => formAction({ name, startedAt: utc, yeastName, yeastMin, yeastMax }));
  }

  return (
    <form onSubmit={submit} noValidate className="flex max-w-sm flex-col gap-4">
      <Field data-invalid={errors.name !== undefined || undefined}>
        <FieldLabel htmlFor="batch-name">Name</FieldLabel>
        <Input
          id="batch-name"
          value={name}
          maxLength={64}
          onChange={(e) => setName(e.target.value)}
          aria-invalid={errors.name !== undefined || undefined}
        />
        <FieldError>{errors.name}</FieldError>
      </Field>
      <Field data-invalid={startReason !== undefined || ended !== null || undefined}>
        <FieldLabel htmlFor="batch-start">Start time</FieldLabel>
        <Input
          id="batch-start"
          type="datetime-local"
          value={start}
          onChange={(e) => setStart(e.target.value)}
          aria-invalid={startReason !== undefined || ended !== null || undefined}
        />
        <FieldError>{startReason}</FieldError>
        {ended !== null && (
          <FieldError>
            {batch ? "It" : "A new batch runs until you end it, so it"} must start after {conflictLink} ended (
            {new Date(ended).toLocaleString()}).
          </FieldError>
        )}
      </Field>
      <Field data-invalid={errors.yeastName !== undefined || undefined}>
        <FieldLabel htmlFor="batch-yeast">Yeast (optional)</FieldLabel>
        <Input
          id="batch-yeast"
          value={yeastName}
          maxLength={64}
          onChange={(e) => setYeastName(e.target.value)}
          aria-invalid={errors.yeastName !== undefined || undefined}
        />
        <FieldError>{errors.yeastName}</FieldError>
      </Field>
      <Field data-invalid={errors.yeastMin !== undefined || undefined}>
        <FieldLabel htmlFor="batch-yeast-min">Yeast min °C</FieldLabel>
        <Input
          id="batch-yeast-min"
          type="number"
          step="any"
          inputMode="decimal"
          value={yeastMin}
          onChange={(e) => setYeastMin(e.target.value)}
          aria-invalid={errors.yeastMin !== undefined || undefined}
        />
        <FieldError>{errors.yeastMin}</FieldError>
      </Field>
      <Field data-invalid={errors.yeastMax !== undefined || undefined}>
        <FieldLabel htmlFor="batch-yeast-max">Yeast max °C</FieldLabel>
        <Input
          id="batch-yeast-max"
          type="number"
          step="any"
          inputMode="decimal"
          value={yeastMax}
          onChange={(e) => setYeastMax(e.target.value)}
          aria-invalid={errors.yeastMax !== undefined || undefined}
        />
        <FieldError>{errors.yeastMax}</FieldError>
      </Field>
      <FieldError>{errors.form}</FieldError>
      {conflict !== null && conflict.endedAt === null && (
        <FieldError>{conflictLink} is already running on this device.</FieldError>
      )}
      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          {batch ? "Save" : "Start batch"}
        </Button>
        <Link
          href={"batch" in props ? `/batches/${props.batch.id}` : `/devices/${props.deviceId}`}
          className={buttonVariants({ variant: "outline" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}
