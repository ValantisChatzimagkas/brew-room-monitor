import { describe, expect, it } from "vitest";

import { yeastSplit } from "./yeast";

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
