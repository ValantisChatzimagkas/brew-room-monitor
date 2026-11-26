"use client";

import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect, NativeSelectOption } from "@/components/ui/native-select";
import { NEW_ROOM, type NewDeviceErrors } from "@/lib/devices";

export type Room = { id: number; name: string };

/** Room picker for an ambient device, with a room-name input when "New room…" is picked. */
export function RoomField({
  rooms,
  room,
  onRoomChange,
  newRoom,
  onNewRoomChange,
  errors,
}: {
  rooms: Room[];
  room: string;
  onRoomChange: (room: string) => void;
  newRoom: string;
  onNewRoomChange: (newRoom: string) => void;
  errors: Pick<NewDeviceErrors, "room" | "newRoom">;
}) {
  return (
    <>
      <Field data-invalid={errors.room !== undefined || undefined}>
        <FieldLabel htmlFor="device-room">Room</FieldLabel>
        <NativeSelect
          id="device-room"
          value={room}
          onChange={(e) => onRoomChange(e.target.value)}
          aria-invalid={errors.room !== undefined || undefined}
        >
          {rooms.map((r) => (
            <NativeSelectOption key={r.id} value={String(r.id)}>
              {r.name}
            </NativeSelectOption>
          ))}
          <NativeSelectOption value={NEW_ROOM}>New room…</NativeSelectOption>
        </NativeSelect>
        <FieldError>{errors.room}</FieldError>
      </Field>
      {room === NEW_ROOM && (
        <Field data-invalid={errors.newRoom !== undefined || undefined}>
          <FieldLabel htmlFor="device-new-room">Room name</FieldLabel>
          <Input
            id="device-new-room"
            value={newRoom}
            maxLength={64}
            onChange={(e) => onNewRoomChange(e.target.value)}
            aria-invalid={errors.newRoom !== undefined || undefined}
          />
          <FieldError>{errors.newRoom}</FieldError>
        </Field>
      )}
    </>
  );
}
