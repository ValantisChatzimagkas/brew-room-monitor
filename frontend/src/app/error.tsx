"use client";

import { useEffect } from "react";

import { REFRESH_MS } from "@/components/auto-refresh";
import { Button } from "@/components/ui/button";

export default function Error({ retry }: { error: unknown; retry: () => void }) {
  // The error boundary unmounts AutoRefresh, so retry on the same interval to recover once the backend answers.
  useEffect(() => {
    const id = setInterval(() => retry(), REFRESH_MS);
    return () => clearInterval(id);
  }, [retry]);

  return (
    <main className="mx-auto max-w-4xl p-6">
      <p className="mb-4">Something went wrong talking to the backend.</p>
      <Button variant="outline" onClick={() => retry()}>
        Retry
      </Button>
    </main>
  );
}
