import { describe, expect, it } from "vitest";

import { deviceStatus } from "./status";

const now = new Date("2026-01-01T12:00:00Z");
const iso = (ms: number) => new Date(now.getTime() - ms).toISOString();
const MIN = 60_000;
const D = 24 * 60 * MIN;

describe("deviceStatus", () => {
  it.each([
    ["active, reading 5 min old", null, [5 * MIN], "ok"],
    ["active, reading 31 min old", null, [31 * MIN], "stale"],
    ["active, no readings", null, [], "ok"],
    ["revoked, reading 5 min old", iso(MIN), [5 * MIN], "revoked"],
    ["revoked, reading 3 days old: supersedes stale", iso(D), [3 * D], "revoked"],
    ["revoked, no readings", iso(D), [], "revoked"],
  ])("%s", (_, revokedAt, ages, expected) => {
    const latest = ages.map((ms) => ({ recorded_at: iso(ms) }));
    expect(deviceStatus({ revoked_at: revokedAt }, latest, now)).toBe(expected);
  });
});
