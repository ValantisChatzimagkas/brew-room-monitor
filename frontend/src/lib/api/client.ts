import "server-only";

import { AccessTokenError } from "@auth0/nextjs-auth0/errors";
import { redirect } from "next/navigation";
import { connection } from "next/server";
import createClient from "openapi-fetch";

import { getAuth0, signInPath } from "@/lib/auth0";

import type { components, paths } from "./schema";

export type Device = components["schemas"]["DevicePublic"];
export type Reading = components["schemas"]["ReadingPublic"];
export type Metric = components["schemas"]["Metric"];
export type BatchCreate = components["schemas"]["BatchCreate"];
export type BatchDetail = components["schemas"]["BatchDetail"];
export type YeastFit = components["schemas"]["YeastFit"];
export type TemperatureNote = components["schemas"]["TemperatureNote"];
export type ReadingBucket = components["schemas"]["ReadingBucket"];
export type BucketSize = components["schemas"]["BucketSize"];
export type DeviceKind = components["schemas"]["DeviceKind"];

// A 401 this soon after sign-in means the backend rejects tokens Auth0 just issued (wrong AUTH_ISSUER or
// AUTH_AUDIENCE), not that the session aged out. Redirecting would loop through Auth0 silently.
const FRESH_SESSION_S = 60;

/**
 * Typed backend client acting as the signed-in user: forwards their access token, so the backend scopes
 * every row to them. Server-only: the token must never reach the browser or a `NEXT_PUBLIC_*` variable.
 * Reads env at request time (not build time) so one Docker image works everywhere.
 * No session, an expired token or a backend 401 redirects to sign-in; nothing is cached across calls (one client per user).
 */
export async function getApi() {
  await connection();
  const baseUrl = process.env.API_URL;
  if (!baseUrl) throw new Error("API_URL must be set");

  let token: string;
  try {
    ({ token } = await getAuth0().getAccessToken());
  } catch (error) {
    if (!(error instanceof AccessTokenError)) throw error;
    redirect(signInPath("/"));
  }

  const client = createClient<paths>({
    baseUrl,
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  client.use({
    async onResponse({ response }) {
      if (response.status !== 401) return;
      const session = await getAuth0().getSession();
      if (session && Date.now() / 1000 - session.internal.createdAt < FRESH_SESSION_S) {
        console.error("Backend rejected a freshly issued user token: check AUTH_ISSUER / AUTH_AUDIENCE");
        throw new Error("Backend rejects new user tokens");
      }
      redirect(signInPath("/"));
    },
  });
  return client;
}

/** No GET /devices/{id}: list at the route's max limit and find. A device beyond the first 500 by name is not found. */
export async function findDevice(id: number): Promise<Device | undefined> {
  const api = await getApi();
  const devices = await api.GET("/api/v1/devices", { params: { query: { limit: 500 } } });
  if (devices.error) throw new Error("Failed to load data from the API");
  return devices.data.find((d) => d.id === id);
}
