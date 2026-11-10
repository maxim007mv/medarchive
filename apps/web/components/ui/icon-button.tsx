"use client";

import * as Tooltip from "@radix-ui/react-tooltip";
import type { LucideIcon } from "lucide-react";
import { useId, type ComponentPropsWithRef, type MouseEvent } from "react";

import { cn } from "./cn";

export type IconButtonProps = Omit<
  ComponentPropsWithRef<"button">,
  "children" | "aria-label" | "disabled"
> & {
  /** Required: an icon alone has no name (TZ-frontend FE-08). Also the hover tooltip. */
  "aria-label": string;
  icon: LucideIcon;
  /** `md` 40 px with a 20 px icon, `sm` 32 px with a 16 px icon. */
  size?: "md" | "sm";
  variant?: "ghost" | "outline";
  /** Rendered with `aria-disabled`; the reason is the description and the tooltip. */
  disabled?: boolean;
  disabledReason?: string;
};

const sizeClasses = {
  md: "size-icon-button",
  sm: "size-icon-button-sm",
} as const;

export function IconButton({
  icon: Icon,
  size = "md",
  variant = "ghost",
  disabled = false,
  disabledReason,
  className,
  onClick,
  type = "button",
  "aria-label": label,
  "aria-describedby": describedBy,
  ...props
}: IconButtonProps) {
  const reasonId = useId();
  const showReason = disabled && Boolean(disabledReason);

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    if (disabled) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  }

  return (
    <Tooltip.Provider delayDuration={400}>
      <Tooltip.Root>
        {/* Hover only (brandbook §13): a focus tooltip stacks over popovers and dialogs and takes
            their Esc. Keyboard and screen reader users get the name from aria-label. */}
        <Tooltip.Trigger asChild onFocus={(event) => event.preventDefault()}>
          <button
            type={type}
            aria-label={label}
            aria-disabled={disabled || undefined}
            aria-describedby={cn(describedBy, showReason && reasonId) || undefined}
            className={cn(
              "inline-flex shrink-0 items-center justify-center rounded-md border",
              "duration-fast transition-colors ease-out",
              sizeClasses[size],
              variant === "outline" ? "border-border bg-surface" : "border-transparent",
              disabled
                ? "text-disabled-text cursor-not-allowed"
                : "text-text2 hover:bg-sunken hover:text-text active:bg-border",
              className,
            )}
            onClick={handleClick}
            {...props}
          >
            <Icon size={size === "md" ? 20 : 16} strokeWidth={1.75} aria-hidden />
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            sideOffset={6}
            className="bg-primary motion-safe:animate-fade-in text-caption text-on-primary shadow-3 z-50 max-w-xs rounded-sm px-2 py-1"
          >
            {showReason ? disabledReason : label}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
      {showReason && (
        <span id={reasonId} hidden>
          {disabledReason}
        </span>
      )}
    </Tooltip.Provider>
  );
}
