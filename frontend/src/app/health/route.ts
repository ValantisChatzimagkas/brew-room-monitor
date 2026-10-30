// Liveness for the container healthcheck. Must not touch the backend or env: `/` does, and fails when the backend is down.
export function GET() {
  return Response.json({ status: "ok" });
}
