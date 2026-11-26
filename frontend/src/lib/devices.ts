import { NAME_MAX, parseId } from "./history";

export const NEW_DEVICE_FIELDS = ["name", "kind", "room", "newRoom"] as const;
type NewDeviceField = (typeof NEW_DEVICE_FIELDS)[number];
/** `room` is a location id as a string, or `""` for none; the others are raw input values. */
export type NewDeviceInput = Record<NewDeviceField, string>;
export type NewDeviceErrors = Partial<Record<NewDeviceField | "form", string>>;
export type NewDevice = { name: string; kind: "in_vessel" } | { name: string; kind: "ambient"; locationId: number };

function isNewDeviceInput(input: unknown): input is NewDeviceInput {
  if (typeof input !== "object" || input === null) return false;
  return NEW_DEVICE_FIELDS.every((field) => typeof Object.getOwnPropertyDescriptor(input, field)?.value === "string");
}

/**
 * The device to register, or why each field can't register it, in the user's words. Mirrors `DeviceCreate`'s
 * length cap and its "ambient needs a room" rule; the backend stays the authority. An `in_vessel` device
 * ignores the room. Rejects anything that isn't the form's shape.
 */
export function parseNewDevice(input: unknown): { device: NewDevice } | { errors: NewDeviceErrors } {
  if (!isNewDeviceInput(input)) return { errors: { form: "Reload the page and try again." } };
  const errors: NewDeviceErrors = {};

  const name = input.name.trim();
  if (name === "") errors.name = "Enter a name.";
  else if (name.length > NAME_MAX) errors.name = "Keep the name to 64 characters.";

  const { kind } = input;
  if (kind !== "ambient" && kind !== "in_vessel") errors.kind = "Pick a kind.";
  const locationId = kind === "ambient" ? parseId(input.room) : null;
  if (kind === "ambient" && locationId === null) errors.room = "Pick a room.";

  if (Object.keys(errors).length > 0) return { errors };
  if (kind === "ambient" && locationId !== null) return { device: { name, kind, locationId } };
  return { device: { name, kind: "in_vessel" } };
}
