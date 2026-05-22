"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: React.ReactNode;
};

export function Dialog({ open, onOpenChange, title, children }: DialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onMouseDown={() => onOpenChange(false)}>
      <div
        className={cn("w-full max-w-2xl rounded-lg border bg-background shadow-xl")}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b p-4">
          <h2 className="text-base font-semibold">{title}</h2>
          <button className="text-sm text-muted-foreground" onClick={() => onOpenChange(false)}>
            Close
          </button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}
