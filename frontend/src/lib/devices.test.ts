import { describe, expect, it } from "vitest";

import { parseNewDevice } from "./devices";

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
