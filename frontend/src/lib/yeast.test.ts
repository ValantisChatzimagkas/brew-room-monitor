import { describe, expect, it } from "vitest";

import { yeastSplit } from "./yeast";

describe("yeastSplit", () => {
  it.each([
    ["no readings", [0, 0, 0], [false, false, false]],
    ["all inside", [0, 5400, 0], [false, false, false]],
    ["some below", [600, 5400, 0], [true, false, false]],
    ["some above", [0, 5400, 60], [false, false, true]],
    ["below and above, none inside", [600, 0, 600], [true, false, true]],
  ])("%s", (_, [below_s, inside_s, above_s], flagged) => {
    expect(yeastSplit({ below_s, inside_s, above_s })).toEqual([
      { label: "below", seconds: below_s, flagged: flagged[0] },
      { label: "inside", seconds: inside_s, flagged: flagged[1] },
      { label: "above", seconds: above_s, flagged: flagged[2] },
    ]);
  });
});
