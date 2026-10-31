import { describe, expect, it } from "vitest";

import { groupByRoom } from "./rooms";

type Item = { name: string; location: { id: number; name: string } | null };
const item = (name: string, location: Item["location"]): Item => ({ name, location });

describe("groupByRoom", () => {
  it("sorts rooms by name, ignoring case", () => {
    const groups = groupByRoom([
      item("a", { id: 1, name: "garage" }),
      item("b", { id: 2, name: "Basement" }),
      item("c", { id: 3, name: "attic" }),
    ]);
    expect(groups.map((g) => g.room)).toEqual(["attic", "Basement", "garage"]);
  });

  it("puts devices without a location in one trailing group", () => {
    const groups = groupByRoom([
      item("a", null),
      item("b", { id: 1, name: "zebra room" }),
      item("c", null),
    ]);
    expect(groups.map((g) => [g.room, g.items.map((i) => i.name)])).toEqual([
      ["zebra room", ["b"]],
      [null, ["a", "c"]],
    ]);
  });

  it("groups by location id and keeps input order within a room", () => {
    const loc = { id: 1, name: "Cellar" };
    const groups = groupByRoom([item("b", loc), item("a", loc)]);
    expect(groups).toHaveLength(1);
    expect(groups[0].items.map((i) => i.name)).toEqual(["b", "a"]);
  });

  it("returns no groups for no items", () => {
    expect(groupByRoom([])).toEqual([]);
  });
});
