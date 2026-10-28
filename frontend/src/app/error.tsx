"use client";

export default function Error({ retry }: { error: unknown; retry: () => void }) {
  return (
    <main className="mx-auto max-w-4xl p-6">
      <p className="mb-4">Something went wrong talking to the backend.</p>
      <button className="rounded border px-3 py-1" onClick={() => retry()}>
        Retry
      </button>
    </main>
  );
}
