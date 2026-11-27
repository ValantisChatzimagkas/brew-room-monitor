"use client";

import Link from "next/link";
import { type FormEvent, startTransition, useActionState, useState } from "react";

import { updateDevice } from "@/app/devices/[id]/settings/actions";
import { type Room, RoomField } from "@/components/room-field";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

/** Form that renames a device and, for an ambient one, moves it to another room. Typed values survive an error. */
export function EditDeviceForm({
  deviceId,
  kind,
  initialName,
  initialRoom,
  rooms,
}: {
  deviceId: number;
  kind: "ambient" | "in_vessel";
  initialName: string;
  initialRoom: string;
  rooms: Room[];
}) {
  const [name, setName] = useState(initialName);
  const [room, setRoom] = useState(initialRoom);
  const [newRoom, setNewRoom] = useState("");
  const [state, formAction, pending] = useActionState(updateDevice.bind(null, deviceId), { errors: {} });
  const { errors } = state;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    startTransition(() => formAction({ name, room, newRoom }));
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
          Save
        </Button>
        <Link href={`/devices/${deviceId}`} className={buttonVariants({ variant: "outline" })}>
          Cancel
        </Link>
      </div>
    </form>
  );
}
