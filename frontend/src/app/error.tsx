"use client";

import { Button } from "@/components/ui/button";

export default function Error({ retry }: { error: unknown; retry: () => void }) {
  return (
    <main className="mx-auto max-w-4xl p-6">
      <p className="mb-4">Something went wrong talking to the backend.</p>
      <Button variant="outline" onClick={() => retry()}>
        Retry
      </Button>
    </main>
  );
}
