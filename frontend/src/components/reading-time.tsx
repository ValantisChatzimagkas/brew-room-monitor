"use client";

import type { ReactNode } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Shows the exact time in the browser's timezone; formatted on render of the open tooltip, so the server's timezone never reaches the HTML. */
export function ReadingTime({ iso, children }: { iso: string; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger className="cursor-default">{children}</TooltipTrigger>
      <TooltipContent>{new Date(iso).toLocaleString()}</TooltipContent>
    </Tooltip>
  );
}
