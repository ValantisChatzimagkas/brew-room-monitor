import "server-only";

import { connection } from "next/server";
import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

export type Device = components["schemas"]["DevicePublic"];
export type Reading = components["schemas"]["ReadingPublic"];
export type Metric = components["schemas"]["Metric"];

/**
 * Typed backend client. Server-only: the admin token must never reach the browser.
 * Reads env at request time (not build time) so one Docker image works everywhere.
 */
export async function getApi() {
  await connection();
  const baseUrl = process.env.API_URL;
  const token = process.env.ADMIN_TOKEN;
  if (!baseUrl || !token) throw new Error("API_URL and ADMIN_TOKEN must be set");

  return createClient<paths>({
    baseUrl,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
}
