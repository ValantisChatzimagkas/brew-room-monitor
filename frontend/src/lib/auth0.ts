import "server-only";

import { Auth0Client } from "@auth0/nextjs-auth0/server";

let client: Auth0Client | undefined;

/**
 * The SDK client, built on first use rather than at import so `next build` and the image work with no
 * AUTH0_* set (env is read at request time). Holds config only, never per-user state.
 * `openid` only: no `offline_access`, so no refresh token, which Server Components could not persist anyway;
 * an expired access token sends the user back through sign-in. The audience makes Auth0 issue a JWT for the API.
 */
export function getAuth0(): Auth0Client {
  if (client) return client;
  const audience = process.env.AUTH_AUDIENCE;
  if (!audience) throw new Error("AUTH_AUDIENCE must be set");
  client = new Auth0Client({
    authorizationParameters: { audience, scope: "openid" },
    enableAccessTokenEndpoint: false,
  });
  return client;
}

export function signInPath(returnTo: string): string {
  return `/auth/login?returnTo=${encodeURIComponent(returnTo)}`;
}
