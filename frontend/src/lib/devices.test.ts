import { describe, expect, it } from "vitest";

import { findRoom, NEW_ROOM, parseNewDevice } from "./devices";

describe("parseNewDevice", () => {
  const base = { name: "Shelf sensor", kind: "ambient", room: "3", newRoom: "" };
  const enterName = { errors: { name: "Enter a name." } };
  const pickRoom = { errors: { room: "Pick a room." } };
  const pickKind = { errors: { kind: "Pick a kind." } };
  it.each([
    [
      "in_vessel, padded name, room ignored",
      { name: " Fermenter 1 ", kind: "in_vessel" },
      { device: { name: "Fermenter 1", kind: "in_vessel" } },
    ],
    ["ambient in an existing room", {}, { device: { name: "Shelf sensor", kind: "ambient", locationId: 3 } }],
    [
      "name of 64 characters",
      { name: "a".repeat(64) },
      { device: { name: "a".repeat(64), kind: "ambient", locationId: 3 } },
    ],
    ["name of 65 characters", { name: "a".repeat(65) }, { errors: { name: "Keep the name to 64 characters." } }],
    ["empty name", { name: "" }, enterName],
    ["name of spaces", { name: "   " }, enterName],
    ["ambient, no room", { room: "" }, pickRoom],
    ["ambient, room not a number", { room: "abc" }, pickRoom],
    ["ambient, room in hex", { room: "0x1" }, pickRoom],
    ["ambient, negative room", { room: "-1" }, pickRoom],
    ["ambient, room beyond the id range", { room: "2147483648" }, pickRoom],
    ["unknown kind", { kind: "sensor" }, pickKind],
    ["empty kind", { kind: "" }, pickKind],
    ["several bad fields", { name: "", room: "" }, { errors: { name: "Enter a name.", room: "Pick a room." } }],
    [
      "ambient in a new room, padded room name",
      { room: NEW_ROOM, newRoom: " Garage " },
      { device: { name: "Shelf sensor", kind: "ambient", newRoom: "Garage" } },
    ],
    [
      "new room name of 64 characters",
      { room: NEW_ROOM, newRoom: "g".repeat(64) },
      { device: { name: "Shelf sensor", kind: "ambient", newRoom: "g".repeat(64) } },
    ],
    [
      "new room name of 65 characters",
      { room: NEW_ROOM, newRoom: "g".repeat(65) },
      { errors: { newRoom: "Keep the room name to 64 characters." } },
    ],
    ["empty new room name", { room: NEW_ROOM, newRoom: "" }, { errors: { newRoom: "Enter a room name." } }],
    ["new room name of spaces", { room: NEW_ROOM, newRoom: "   " }, { errors: { newRoom: "Enter a room name." } }],
    [
      "in_vessel ignores an empty new room",
      { kind: "in_vessel", room: NEW_ROOM, newRoom: "" },
      { device: { name: "Shelf sensor", kind: "in_vessel" } },
    ],
  ])("%s", (_, over, expected) => {
    expect(parseNewDevice({ ...base, ...over })).toEqual(expected);
  });

  it.each([
    ["not an object", "x"],
    ["null", null],
    ["a field missing", { name: "Shelf sensor", kind: "ambient", room: "3" }],
    ["a field not a string", { ...base, room: 3 }],
  ])("%s -> reload", (_, input) => {
    expect(parseNewDevice(input)).toEqual({ errors: { form: "Reload the page and try again." } });
  });
});

describe("findRoom", () => {
  const garage = { id: 1, name: "Garage" };
  it.each([
    ["exact name", [garage], "Garage", garage],
    ["other case", [garage], "garage", garage],
    ["padded, upper case", [garage], " GARAGE ", garage],
    ["no match", [garage], "Cellar", undefined],
    ["no rooms", [], "Garage", undefined],
  ])("%s", (_, rooms, name, expected) => {
    expect(findRoom(rooms, name)).toBe(expected);
  });
});
