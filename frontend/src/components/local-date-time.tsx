"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/** False during the server render and hydration, true after: gates output that depends on the browser. */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}

/**
 * A date and time in the browser's timezone and locale. The text fills in only after hydration: the server's
 * timezone isn't the user's, so its HTML holds just the `<time>` element.
 */
export function LocalDateTime({ iso }: { iso: string }) {
  const hydrated = useHydrated();
  return (
    <time dateTime={iso}>
      {hydrated ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : null}
    </time>
  );
}
