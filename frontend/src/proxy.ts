import { NextResponse, type NextRequest } from "next/server";

import { getAuth0, signInPath } from "@/lib/auth0";

// Optimistic gate: a real 307 for anonymous visitors. `getApi()` re-checks, so a path missed here leaks no data.
export async function proxy(request: NextRequest): Promise<NextResponse> {
  const response = await getAuth0().middleware(request);
  const { pathname, search } = request.nextUrl;
  if (pathname.startsWith("/auth/")) return response;

  if (!(await getAuth0().getSession(request))) {
    // Both nextUrl and request.url carry the internal host (0.0.0.0 in the container); Next relativizes a
    // same-host redirect, so the internal host never reaches the browser.
    const url = request.nextUrl.clone();
    const target = new URL(signInPath(pathname + search), url);
    return NextResponse.redirect(target);
  }
  return response;
}

export const config = {
  matcher: ["/((?!health|_next/static|_next/image|favicon.ico).*)"],
};
