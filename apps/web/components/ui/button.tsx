"use client";

import { LoaderCircle, type LucideIcon } from "lucide-react";
import { useId, type ComponentPropsWithRef, type MouseEvent } from "react";

import { cn } from "./cn";

export type ButtonVariant = "primary" | "secondary" | "tertiary" | "danger" | "dangerText";
export type ButtonSize = "sm" | "md" | "lg";

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-control-sm rounded-md px-3 text-label",
  md: "h-control-md rounded-lg px-4 text-body font-medium",
  lg: "h-control-lg rounded-lg px-5 text-button-lg",
};

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "border-transparent bg-primary text-on-primary hover:bg-primary-hover active:bg-primary-active",
  secondary: "border-border bg-surface text-text shadow-1 hover:bg-sunken",
  tertiary: "border-transparent bg-transparent text-text hover:bg-sunken",
  // onPrimary is white in the light theme and #171717 in the dark one, as brandbook §5 wants.
  danger: "border-transparent bg-danger text-on-primary hover:brightness-110 active:brightness-95",
  dangerText: "border-transparent bg-transparent text-danger hover:bg-danger-bg",
};

const isTextVariant = (variant: ButtonVariant) =>
  variant === "tertiary" || variant === "dangerText";

/** Classes of a button, for links that look like one (`<a href download>`). */
export function buttonClasses({
  variant = "primary",
  size = "md",
  disabled = false,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
}): string {
  const stateClasses = disabled
    ? cn(
        "cursor-not-allowed border-transparent text-disabled-text",
        isTextVariant(variant) ? "bg-transparent" : "bg-disabled-bg",
      )
    : variantClasses[variant];
  return cn(
    "inline-grid shrink-0 place-items-center border whitespace-nowrap select-none",
    "transition-colors duration-fast ease-out",
    sizeClasses[size],
    stateClasses,
  );
}

export type ButtonProps = Omit<ComponentPropsWithRef<"button">, "disabled"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Leading icon: 16 px in `sm`, 20 px otherwise. */
  icon?: LucideIcon;
  /** Spinner and `loadingText` replace the label; the width stays that of the wider one. */
  loading?: boolean;
  loadingText?: string;
  /**
   * Rendered with `aria-disabled`, so the button stays focusable and its reason is announced.
   * If the layout shows the reason as visible text, pass that element in `aria-describedby`.
   */
  disabled?: boolean;
  disabledReason?: string;
};

export function Button({
  variant = "primary",
  size = "md",
  icon: Icon,
  loading = false,
  loadingText,
  disabled = false,
  disabledReason,
  className,
  children,
  onClick,
  type = "button",
  "aria-describedby": describedBy,
  ...props
}: ButtonProps) {
  const reasonId = useId();
  const showReason = disabled && Boolean(disabledReason);
  const iconSize = size === "sm" ? 16 : 20;
  const layer = "col-start-1 row-start-1 inline-flex items-center gap-2";

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    // aria-disabled does not stop clicks or implicit form submission by itself.
    if (disabled || loading) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  }

  return (
    <>
      <button
        type={type}
        aria-disabled={disabled || loading || undefined}
        aria-busy={loading || undefined}
        aria-describedby={cn(describedBy, showReason && reasonId) || undefined}
        className={cn(
          buttonClasses({ variant, size, disabled }),
          loading && "cursor-wait",
          className,
        )}
        onClick={handleClick}
        {...props}
      >
        <span className={cn(layer, loading && "invisible")} aria-hidden={loading || undefined}>
          {Icon && <Icon size={iconSize} strokeWidth={1.75} aria-hidden />}
          {children}
        </span>
        <span className={cn(layer, !loading && "invisible")} aria-hidden={!loading || undefined}>
          <LoaderCircle
            size={16}
            strokeWidth={1.75}
            className="motion-safe:animate-spin"
            aria-hidden
          />
          {loadingText ?? children}
        </span>
      </button>
      {showReason && (
        <span id={reasonId} hidden>
          {disabledReason}
        </span>
      )}
    </>
  );
}
