"use client";

import Link from "next/link";
import { useSelectedLayoutSegment } from "next/navigation";

import { buttonVariants } from "@/components/ui/button";

type Section = "dashboard" | "batches";

/** Header links; marks the current section. Suspends on dynamic routes, so render it inside `<Suspense>`. */
export function SiteNav() {
  const segment = useSelectedLayoutSegment();
  // Device pages are reached from the Dashboard, so they count as it; so do unmatched URLs.
  const current: Section = segment === "batches" ? "batches" : "dashboard";
  return <SiteNavLinks current={current} />;
}

/** The links alone, so the Suspense fallback can render them with nothing marked. */
export function SiteNavLinks({ current }: { current: Section | null }) {
  return (
    <nav aria-label="Main" className="flex gap-2">
      <NavLink href="/" active={current === "dashboard"}>
        Dashboard
      </NavLink>
      <NavLink href="/batches" active={current === "batches"}>
        Batches
      </NavLink>
    </nav>
  );
}

function NavLink({ href, active, children }: { href: string; active: boolean; children: string }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={buttonVariants({ variant: active ? "default" : "outline", size: "sm" })}
    >
      {children}
    </Link>
  );
}
