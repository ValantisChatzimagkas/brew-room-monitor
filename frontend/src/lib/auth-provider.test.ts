import { describe, expect, it } from "vitest";

import { allowInsecureProvider } from "./auth-provider";

const local = "http://oidc.localhost:9400/default";

describe("allowInsecureProvider", () => {
  it.each([
    ["http provider, local", local, "local", true],
    ["http provider, environment unset", local, undefined, true],
    ["scheme in upper case", "HTTP://oidc.localhost:9400/default", "local", true],
    ["https tenant, production", "https://tenant.auth0.com", "production", false],
    ["bare tenant host, production", "tenant.auth0.com", "production", false],
    ["bare tenant host, local", "tenant.auth0.com", "local", false],
    ["domain unset", undefined, "local", false],
  ])("%s", (_, domain, environment, expected) => {
    expect(allowInsecureProvider(domain, environment)).toBe(expected);
  });

  it.each([local, "HTTP://x"])("refuses %s in production", (domain) => {
    expect(() => allowInsecureProvider(domain, "production")).toThrow(/https:\/\/ in production/);
  });
});
