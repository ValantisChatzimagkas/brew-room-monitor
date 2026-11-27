import { hasStringFields, NAME_MAX, parseId } from "./history";

export const FIRMWARE_DOCS =
  "https://github.com/ValantisChatzimagkas/brew-room-monitor/blob/main/firmware/README.md#2-send-readings";

/** The room picker's value for a room typed on the form. */
export const NEW_ROOM = "new";

export const NEW_DEVICE_FIELDS = ["name", "kind", "room", "newRoom"] as const;
type NewDeviceField = (typeof NEW_DEVICE_FIELDS)[number];
/** `room` is a location id as a string, `""` for none, or `NEW_ROOM`; the others are raw input values. */
export type NewDeviceInput = Record<NewDeviceField, string>;
export type NewDeviceErrors = Partial<Record<NewDeviceField | "form", string>>;
export type NewDevice =
  | { name: string; kind: "in_vessel" }
  | { name: string; kind: "ambient"; locationId: number }
  | { name: string; kind: "ambient"; newRoom: string };

/**
 * The device to register, or why each field can't register it, in the user's words. Mirrors the length caps
 * of `DeviceCreate` and `LocationCreate` and the "ambient needs a room" rule; the backend stays the
 * authority. An `in_vessel` device ignores the room. Rejects anything that isn't the form's shape.
 */
export function parseNewDevice(input: unknown): { device: NewDevice } | { errors: NewDeviceErrors } {
  if (!hasStringFields(input, NEW_DEVICE_FIELDS)) return { errors: { form: "Reload the page and try again." } };
  const errors: NewDeviceErrors = {};

  const name = input.name.trim();
  if (name === "") errors.name = "Enter a name.";
  else if (name.length > NAME_MAX) errors.name = "Keep the name to 64 characters.";

  const { kind } = input;
  if (kind !== "ambient" && kind !== "in_vessel") errors.kind = "Pick a kind.";
  const isNewRoom = kind === "ambient" && input.room === NEW_ROOM;
  const newRoom = input.newRoom.trim();
  if (isNewRoom && newRoom === "") errors.newRoom = "Enter a room name.";
  else if (isNewRoom && newRoom.length > NAME_MAX) errors.newRoom = "Keep the room name to 64 characters.";
  const locationId = kind === "ambient" && !isNewRoom ? parseId(input.room) : null;
  if (kind === "ambient" && !isNewRoom && locationId === null) errors.room = "Pick a room.";

  if (Object.keys(errors).length > 0) return { errors };
  if (isNewRoom) return { device: { name, kind: "ambient", newRoom } };
  if (kind === "ambient" && locationId !== null) return { device: { name, kind, locationId } };
  return { device: { name, kind: "in_vessel" } };
}

export const EDIT_DEVICE_FIELDS = ["name", "room", "newRoom"] as const;
/** The edit form's input: like `NewDeviceInput`, without `kind`, which can't change. */
export type EditDeviceInput = Record<(typeof EDIT_DEVICE_FIELDS)[number], string>;

/**
 * The device's new name and room, or why each field can't save, by the rules of `parseNewDevice`. `kind` is
 * the stored device's: one sent with the input is never read, so it can't drop an ambient device's room.
 */
export function parseDeviceEdit(
  input: unknown,
  kind: "ambient" | "in_vessel",
): { device: NewDevice } | { errors: NewDeviceErrors } {
  if (!hasStringFields(input, EDIT_DEVICE_FIELDS)) return { errors: { form: "Reload the page and try again." } };
  return parseNewDevice({ name: input.name, kind, room: input.room, newRoom: input.newRoom });
}

/**
 * The room with this name, ignoring case and surrounding spaces, like the backend's unique name check
 * (strip + Postgres `lower()`); a character the two fold differently is simply not found.
 */
export function findRoom<R extends { name: string }>(rooms: readonly R[], name: string): R | undefined {
  const key = name.trim().toLowerCase();
  return rooms.find((room) => room.name.trim().toLowerCase() === key);
}
