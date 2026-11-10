"use client";

import * as Popover from "@radix-ui/react-popover";
import { Ellipsis, Trash2 } from "lucide-react";
import { useState } from "react";

import { IconButton } from "@/components/ui/icon-button";
import { texts } from "@/lib/texts";

/**
 * «Ещё» of a row or card (D06, M02): the only item is «Удалить», hidden one step deeper on purpose
 * (11-design-rationale, «Удалить»). Closing returns focus to the trigger, so the delete dialog
 * hands focus back to it after Esc (TC-056).
 */
export function RowMenu({
  onDelete,
  disabledReason,
  label = texts["list.row.more"],
}: {
  onDelete: () => void;
  disabledReason?: string;
  label?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <IconButton icon={Ellipsis} size="sm" aria-label={label} aria-haspopup="menu" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={4}
          role="menu"
          className="animate-fade-in bg-raised shadow-3 z-30 flex min-w-40 flex-col rounded-lg p-1"
        >
          <button
            type="button"
            role="menuitem"
            aria-disabled={disabledReason ? true : undefined}
            title={disabledReason}
            onClick={() => {
              if (disabledReason) return;
              setOpen(false);
              onDelete();
            }}
            className="h-control-sm text-body text-danger hover:bg-danger-bg focus-visible:bg-danger-bg aria-disabled:text-disabled-text flex items-center gap-2 rounded-md px-2.5 aria-disabled:cursor-not-allowed aria-disabled:hover:bg-transparent"
          >
            <Trash2 size={16} strokeWidth={1.75} aria-hidden />
            {texts["list.row.menu.delete"]}
          </button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
