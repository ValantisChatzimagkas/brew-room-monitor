"use client";

import Link from "next/link";
import { type FormEvent, startTransition, useActionState, useState } from "react";

import { registerDevice } from "@/app/devices/new/actions";
import { DeviceToken, useResetOnHide } from "@/components/device-token";
import { type Room, RoomField } from "@/components/room-field";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { DEVICE_KIND_LABEL, FIRMWARE_DOCS, NEW_ROOM } from "@/lib/devices";

/**
 * Form that registers a device and then shows its token once. The token lives only in the inner form's
 * action state, so re-keying the inner form drops it.
 */
export function RegisterDeviceForm({ rooms }: { rooms: Room[] }) {
  const [formKey, reset] = useResetOnHide();
  return <OpenForm key={formKey} rooms={rooms} onReset={reset} />;
}

function OpenForm({ rooms, onReset }: { rooms: Room[]; onReset: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState("ambient");
  const [room, setRoom] = useState(rooms[0] ? String(rooms[0].id) : NEW_ROOM);
  const [newRoom, setNewRoom] = useState("");
  const [state, formAction, pending] = useActionState(registerDevice, { errors: {}, created: null });
  const { errors, created } = state;

  if (created) {
    return (
      <div className="flex max-w-xl flex-col gap-4">
        <p>
          <span className="font-medium">{created.name}</span> is registered.
        </p>
        <DeviceToken token={created.token} />
        <div className="flex flex-wrap gap-2">
          <Link href={`/devices/${created.id}`} className={buttonVariants()}>
            Open {created.name}
          </Link>
          <Link href="/" className={buttonVariants({ variant: "outline" })}>
            Dashboard
          </Link>
          <a
            href={FIRMWARE_DOCS}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({ variant: "outline" })}
          >
            How to flash it
          </a>
          <Button variant="outline" onClick={onReset}>Register another</Button>
        </div>
      </div>
    );
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    startTransition(() => formAction({ name, kind, room, newRoom }));
  }

  return (
    <form onSubmit={submit} noValidate className="flex max-w-sm flex-col gap-4">
      <Field data-invalid={errors.name !== undefined || undefined}>
        <FieldLabel htmlFor="device-name">Name</FieldLabel>
        <Input
          id="device-name"
          value={name}
          maxLength={64}
          onChange={(e) => setName(e.target.value)}
          aria-invalid={errors.name !== undefined || undefined}
        />
        <FieldError>{errors.name}</FieldError>
      </Field>
      <Field data-invalid={errors.kind !== undefined || undefined}>
        <FieldLabel htmlFor="device-kind">Kind</FieldLabel>
        <NativeSelect
          id="device-kind"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          aria-invalid={errors.kind !== undefined || undefined}
        >
          <NativeSelectOption value="ambient">{DEVICE_KIND_LABEL.ambient} (measures a room)</NativeSelectOption>
          <NativeSelectOption value="in_vessel">{DEVICE_KIND_LABEL.in_vessel} (floats in the fermenter)</NativeSelectOption>
        </NativeSelect>
        <FieldError>{errors.kind}</FieldError>
      </Field>
      {kind === "ambient" && (
        <RoomField
          rooms={rooms}
          room={room}
          onRoomChange={setRoom}
          newRoom={newRoom}
          onNewRoomChange={setNewRoom}
          errors={errors}
        />
      )}
      <FieldError>{errors.form}</FieldError>
      <div className="flex gap-2">
        <Button type="submit" disabled={pending}>
          Register device
        </Button>
        <Link href="/" className={buttonVariants({ variant: "outline" })}>
          Cancel
        </Link>
      </div>
    </form>
  );
}
