"use client";

import { Check, Copy } from "lucide-react";
import { useLayoutEffect, useState } from "react";
import { flushSync } from "react-dom";

import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const next = (key: number) => key + 1;

/**
 * A key for the component that holds a token shown once, and a function that bumps it. Re-keying that
 * component drops the token from its action state.
 */
export function useResetOnHide(): [key: number, reset: () => void] {
  const [key, setKey] = useState(0);
  // The token must never come back: Next keeps a hidden route mounted in <Activity> (this cleanup runs on
  // hide), and the browser's back/forward cache keeps the whole page (pagehide, flushed so the snapshot
  // holds no token). Empty deps: a `refresh()` that changes the page's data must not clear the token on screen.
  useLayoutEffect(() => {
    const onPageHide = () => flushSync(() => setKey(next));
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      setKey(next);
    };
  }, []);
  return [key, () => setKey(next)];
}

export function DeviceToken({ token }: { token: string }) {
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");

  async function copyToken() {
    try {
      // `navigator.clipboard` is undefined outside a secure context (plain HTTP on the LAN): that throws here too.
      await navigator.clipboard.writeText(token);
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
  }

  return (
    <Field>
      <FieldLabel htmlFor="device-token">Device token</FieldLabel>
      <p className="text-sm font-medium text-destructive">
        Copy this token now. It won&apos;t be shown again. Flash it into the device config, not into git.
      </p>
      <div className="flex gap-2">
        <Input
          id="device-token"
          value={token}
          readOnly
          onFocus={(e) => e.currentTarget.select()}
          className="font-mono"
        />
        <Button variant="outline" onClick={copyToken}>
          {copy === "copied" ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
          {copy === "copied" ? "Copied" : "Copy"}
        </Button>
      </div>
      {copy === "failed" && <FieldError>Copy didn&apos;t work here. Select the token and copy it.</FieldError>}
    </Field>
  );
}
