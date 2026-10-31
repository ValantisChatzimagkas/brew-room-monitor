import { describe, expect, it } from "vitest";

import { formatAge, isStale, STALE_AFTER_MS } from "./time";

const now = new Date("2026-01-01T12:00:00Z");
const ago = (ms: number) => new Date(now.getTime() - ms);
const iso = (ms: number) => ago(ms).toISOString();
const S = 1000;
const MIN = 60 * S;
const H = 60 * MIN;
const D = 24 * H;

describe("formatAge", () => {
  it.each([
    ["now", 0, "just now"],
    ["future (device clock skew)", -3 * MIN, "just now"],
    ["59 s", 59 * S, "just now"],
    ["60 s", 60 * S, "1 min ago"],
    ["59 min 59 s", 59 * MIN + 59 * S, "59 min ago"],
    ["60 min", 60 * MIN, "1 h ago"],
    ["23 h 59 min", 23 * H + 59 * MIN, "23 h ago"],
    ["24 h", 24 * H, "1 d ago"],
    ["3 days", 3 * D, "3 d ago"],
  ])("%s", (_, ms, expected) => {
    expect(formatAge(ago(ms), now)).toBe(expected);
  });
});

describe("isStale", () => {
  it.each([
    ["29 min 59 s", [29 * MIN + 59 * S], false],
    ["exactly 30 min", [STALE_AFTER_MS], false],
    ["30 min 1 s", [STALE_AFTER_MS + S], true],
    ["5 days", [5 * D], true],
    ["no readings", [], false],
    ["newest decides: 5 days and 1 min", [5 * D, MIN], false],
    ["all older than 30 min", [5 * D, 2 * H], true],
  ])("%s", (_, ages, expected) => {
    expect(isStale(ages.map((ms) => ({ recorded_at: iso(ms) })), now)).toBe(expected);
  });
});
