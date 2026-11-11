import { CircleCheck, Info, TriangleAlert, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "./cn";

export type AlertVariant = "info" | "warn" | "danger" | "success";

const variants: Record<AlertVariant, { icon: LucideIcon; classes: string }> = {
  info: { icon: Info, classes: "bg-sunken text-text2" },
  warn: { icon: TriangleAlert, classes: "bg-warn-bg text-warn" },
  danger: { icon: TriangleAlert, classes: "bg-danger-bg text-danger" },
  success: { icon: CircleCheck, classes: "bg-success-bg text-success" },
};

export type AlertProps = {
  variant: AlertVariant;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
};

/**
 * Message block inside a form or under the list (FE-09). `danger` is `role="alert"`, so an error
 * that appears is announced; the others are part of the page and stay silent.
 */
export function Alert({ variant, title, children, action, className }: AlertProps) {
  const { icon: Icon, classes } = variants[variant];

  return (
    <div
      role={variant === "danger" ? "alert" : undefined}
      className={cn(
        "text-label flex items-start gap-3 rounded-lg p-3 font-normal",
        classes,
        className,
      )}
    >
      <Icon size={16} strokeWidth={1.75} className="mt-0.5 shrink-0" aria-hidden />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div>{children}</div>}
      </div>
      {action}
    </div>
  );
}
