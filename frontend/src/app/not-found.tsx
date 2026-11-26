import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="mx-auto w-full max-w-4xl p-6">
      <h1 className="mb-2 text-2xl font-semibold">Not found</h1>
      {/* "isn't yours": a foreign id must look the same as a missing one. */}
      <p className="mb-4 text-muted-foreground">This page doesn&apos;t exist, or it isn&apos;t yours.</p>
      <Link href="/" className={buttonVariants({ variant: "outline" })}>
        Back to the Dashboard
      </Link>
    </main>
  );
}
