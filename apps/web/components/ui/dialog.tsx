"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useLayoutEffect, useRef, type ReactNode, type RefObject } from "react";

import { texts } from "@/lib/texts";

import { cn } from "./cn";
import { IconButton } from "./icon-button";

export type DialogProps = {
  open: boolean;
  /** Esc, the cross and the scrim call it with `false`; ignore it to ask «Закрыть без сохранения?». */
  onOpenChange: (open: boolean) => void;
  /** «Глагол + объект?» for confirmations (brandbook §9). */
  title: string;
  description?: ReactNode;
  /** From 768 px: `form` 560 px or `confirm` 440 px wide. Below that it is a bottom sheet. */
  width?: "form" | "confirm";
  /** Focused on open instead of the cross, e.g. «Отмена» in a delete confirmation. */
  initialFocus?: RefObject<HTMLElement | null>;
  /** Focused on close when the element to return to has left the page. */
  finalFocus?: RefObject<HTMLElement | null>;
  /**
   * Opens in the same render in which another dialog closes. The scrim is already on screen, so
   * it does not fade in again, and focus later returns to where the closed dialog would return it.
   */
  handOff?: boolean;
  /** Buttons: «Отмена» first, the action last. Desktop puts them right, the sheet stacks them. */
  footer?: ReactNode;
  children?: ReactNode;
};

/** Return target of the dialog that closed last, for a `handOff` dialog opening after it. */
let closedDialogReturnTo: Element | null = null;

function isFocusable(element: Element | null | undefined): element is HTMLElement {
  return element instanceof HTMLElement && element !== document.body && element.isConnected;
}

/**
 * Modal from 768 px, bottom sheet below (FE-06). Radix traps focus, closes on Esc and returns
 * focus to the element that was focused before opening.
 */
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  width = "form",
  initialFocus,
  finalFocus,
  handOff = false,
  footer,
  children,
}: DialogProps) {
  // Radix returns focus only to a Dialog.Trigger; our dialogs open from any button or menu.
  const returnFocusTo = useRef<Element | null>(null);

  // Capture the opener before Radix moves focus (onOpenAutoFocus already sees the dialog).
  // Cleanup runs before the next dialog's layout effect in the same commit, so a hand-off
  // inherits this return target instead of finalFocus. A parent that unmounts on close (export,
  // upload) never flips `open` to false, so Radix skips onCloseAutoFocus — restore here.
  useLayoutEffect(() => {
    if (!open) return;
    returnFocusTo.current = handOff ? closedDialogReturnTo : document.activeElement;
    return () => {
      closedDialogReturnTo = returnFocusTo.current;
      const target = returnFocusTo.current;
      const fallback = finalFocus?.current;
      queueMicrotask(() => {
        if (document.activeElement?.closest('[role="dialog"]')) return;
        if (isFocusable(target)) target.focus();
        else fallback?.focus();
      });
    };
  }, [open, handOff, finalFocus]);

  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay
          className={cn(
            "bg-scrim fixed inset-0 z-40 flex items-end justify-center pt-12 md:items-center md:p-8",
            !handOff && "motion-safe:animate-fade-in",
          )}
        >
          <RadixDialog.Content
            // Without a description Radix would point aria-describedby at a missing element.
            {...(description ? {} : { "aria-describedby": undefined })}
            onOpenAutoFocus={(event) => {
              if (!initialFocus?.current) return;
              event.preventDefault();
              initialFocus.current.focus();
            }}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              // Radix calls this a task after unmount; a dialog that took over has focused itself by then.
              if (document.activeElement?.closest('[role="dialog"]')) return;
              const target = isFocusable(returnFocusTo.current)
                ? returnFocusTo.current
                : finalFocus?.current;
              target?.focus();
            }}
            className={cn(
              "bg-raised pb-safe motion-safe:animate-sheet-in text-text shadow-dialog relative flex max-h-full w-full flex-col rounded-t-2xl",
              "md:motion-safe:animate-dialog-in md:rounded-2xl md:pb-6",
              width === "form" ? "md:max-w-dialog-form" : "md:max-w-dialog-confirm",
            )}
          >
            <div
              aria-hidden
              className="bg-border mx-auto mt-2 h-1 w-9 shrink-0 rounded-full md:hidden"
            />
            <div className="flex flex-col gap-2 px-4 pt-4 pr-12 md:px-6 md:pt-6 md:pr-12">
              <RadixDialog.Title className="text-h2">{title}</RadixDialog.Title>
              {description && (
                <RadixDialog.Description className="text-body text-text2">
                  {description}
                </RadixDialog.Description>
              )}
            </div>
            {children && (
              // Focus ring is 2 px + 2 px offset: keep it inside the scroll box (clips overflow).
              <div className="-mb-2 flex min-h-0 flex-col gap-4 overflow-y-auto px-4 pt-5 pb-2 md:px-6">
                {children}
              </div>
            )}
            {footer && (
              <div
                className={cn(
                  "flex flex-col-reverse gap-2 px-4 pt-4 md:flex-row md:justify-end md:px-6",
                  // Sheet buttons are full-width main actions: 48 px (TZ-frontend §4).
                  "max-md:*:h-control-lg max-md:*:text-button-lg max-md:*:w-full",
                )}
              >
                {footer}
              </div>
            )}
            {/* Last in the DOM, so initial focus lands on the content, not on the cross. */}
            <RadixDialog.Close asChild>
              <IconButton
                icon={X}
                size="sm"
                aria-label={texts["common.close"]}
                className="absolute top-6 right-2.5 md:top-5 md:right-5"
              />
            </RadixDialog.Close>
          </RadixDialog.Content>
        </RadixDialog.Overlay>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}

/** Closes the dialog it sits in; wrap a footer «Отмена» button with it. */
export const DialogClose = RadixDialog.Close;
