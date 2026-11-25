import { describe, expect, it } from "vitest";

import { yeastPosition, yeastSplit } from "./yeast";

describe("yeastSplit", () => {
  it.each([
    ["no readings", [0, 0, 0], [false, false, false]],
    ["all inside", [0, 5, 0], [false, false, false]],
    ["some below", [2, 5, 0], [true, false, false]],
    ["some above", [0, 5, 1], [false, false, true]],
    ["below and above, none inside", [1, 0, 1], [true, false, true]],
  ])("%s", (_, [below, inside, above], flagged) => {
    expect(yeastSplit({ below, inside, above })).toEqual([
      { label: "below", count: below, flagged: flagged[0] },
      { label: "inside", count: inside, flagged: flagged[1] },
      { label: "above", count: above, flagged: flagged[2] },
    ]);
  });
});

describe("yeastPosition", () => {
  it.each([
    [{ min: 18, max: 22 }, 17.9, "below"],
    [{ min: 18, max: 22 }, 18, "inside"],
    [{ min: 18, max: 22 }, 20, "inside"],
    [{ min: 18, max: 22 }, 22, "inside"],
    [{ min: 18, max: 22 }, 22.1, "above"],
    [{ min: 20, max: 20 }, 20, "inside"],
    [{ min: 20, max: 20 }, 19.9, "below"],
    [{ min: 20, max: 20 }, 20.1, "above"],
  ])("%j, %d -> %s", (range, value, expected) => {
    expect(yeastPosition(value, range)).toBe(expected);
  });
});
