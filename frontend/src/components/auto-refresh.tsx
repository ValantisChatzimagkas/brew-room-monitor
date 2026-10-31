"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export const REFRESH_MS = 60_000;

/** Re-renders the server components on an interval so readings stay current without a manual reload. */
export function AutoRefresh() {
  const router = useRouter();
  useEffect(() => {
    const id = setInterval(() => router.refresh(), REFRESH_MS);
    return () => clearInterval(id);
  }, [router]);
  return null;
}
