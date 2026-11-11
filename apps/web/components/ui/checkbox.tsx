"use client";

import * as RadixCheckbox from "@radix-ui/react-checkbox";
import { Check, Minus } from "lucide-react";
import type { ComponentPropsWithRef, ReactNode } from "react";

import { cn } from "./cn";

type CheckboxRootProps = Omit<
  ComponentPropsWithRef<typeof RadixCheckbox.Root>,
  "children" | "className" | "aria-label"
>;

export type CheckboxProps = CheckboxRootProps &
  ({ label: ReactNode; "aria-label"?: undefined } | { label?: undefined; "aria-label": string }) & {
    className?: string;
  };

/** Yes/no choice (FE-05). With a `label` the whole line is clickable. */
export function Checkbox({ label, className, ...props }: CheckboxProps) {
  const box = (
    <RadixCheckbox.Root
      {...props}
      className={cn(
        "group border-control bg-surface grid size-4.5 shrink-0 place-items-center rounded-xs border-2",
        "text-on-primary duration-fast transition-colors ease-out",
        "data-[state=checked]:border-primary data-[state=checked]:bg-primary",
        "data-[state=indeterminate]:border-primary data-[state=indeterminate]:bg-primary",
        "disabled:border-border disabled:bg-sunken disabled:cursor-not-allowed",
        !label && className,
      )}
    >
      <RadixCheckbox.Indicator>
        <Check
          size={14}
          strokeWidth={3}
          className="group-data-[state=indeterminate]:hidden"
          aria-hidden
        />
        <Minus
          size={14}
          strokeWidth={3}
          className="hidden group-data-[state=indeterminate]:block"
          aria-hidden
        />
      </RadixCheckbox.Indicator>
    </RadixCheckbox.Root>
  );

  if (!label) return box;
  return (
    <label
      className={cn(
        "text-body text-text inline-flex cursor-pointer items-center gap-2.5",
        "has-disabled:text-text3 has-disabled:cursor-not-allowed",
        className,
      )}
    >
      {box}
      {label}
    </label>
  );
}
