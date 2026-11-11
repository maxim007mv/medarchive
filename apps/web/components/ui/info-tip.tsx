"use client";

import * as Popover from "@radix-ui/react-popover";
import { Info } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

/**
 * «i» next to a label: the explanation opens on hover, on keyboard focus and on a tap, and Esc or
 * a press elsewhere closes it. Focus stays on the button, which the explanation describes.
 */
export function InfoTip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const contentId = useId();

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      {/* An anchor, not Popover.Trigger: a trigger toggles on click, which would close the
          explanation that focus has just opened. */}
      <Popover.Anchor asChild>
        <button
          type="button"
          aria-label={label}
          aria-expanded={open}
          aria-describedby={open ? contentId : undefined}
          onPointerEnter={(event) => event.pointerType === "mouse" && setOpen(true)}
          onPointerLeave={(event) => event.pointerType === "mouse" && setOpen(false)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onClick={() => setOpen(true)}
          className="text-text3 hover:text-text duration-fast inline-grid size-6 place-items-center rounded-full transition-colors"
        >
          <Info size={16} strokeWidth={1.75} aria-hidden />
        </button>
      </Popover.Anchor>
      <Popover.Portal>
        <Popover.Content
          id={contentId}
          role="tooltip"
          side="top"
          align="start"
          sideOffset={6}
          onOpenAutoFocus={(event) => event.preventDefault()}
          onCloseAutoFocus={(event) => event.preventDefault()}
          className="bg-raised shadow-3 text-caption text-text motion-safe:animate-fade-in z-50 max-w-xs rounded-lg p-3"
        >
          {children}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
