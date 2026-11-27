import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Suspense } from "react";
import "./globals.css";

import { SiteNav, SiteNavLinks } from "@/components/site-nav";
import { buttonVariants } from "@/components/ui/button";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Brew Room Monitor",
  description: "Brewing room conditions and yeast insights",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="mx-auto flex w-full max-w-4xl items-center justify-between px-6 pt-4">
          <Suspense fallback={<SiteNavLinks current={null} />}>
            <SiteNav />
          </Suspense>
          {/* A plain <a>, not <Link>: the SDK's logout route must not be prefetched. */}
          <a href="/auth/logout" className={buttonVariants({ variant: "outline", size: "sm" })}>
            Sign out
          </a>
        </header>
        {children}
      </body>
    </html>
  );
}
