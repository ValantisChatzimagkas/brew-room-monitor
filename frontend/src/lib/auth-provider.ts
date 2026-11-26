/**
 * Whether the SDK may talk to the sign-in provider over plain HTTP (`allowInsecureRequests`).
 * The SDK needs it for the local provider (`http://oidc.localhost:...`); production refuses an
 * `http://` provider, as `backend/app/config.py` does for `AUTH_ISSUER`. The message never echoes the value.
 */
export function allowInsecureProvider(domain: string | undefined, environment: string | undefined): boolean {
  const insecure = domain?.toLowerCase().startsWith("http://") ?? false;
  if (insecure && environment === "production") throw new Error("AUTH0_DOMAIN must use https:// in production");
  return insecure;
}
