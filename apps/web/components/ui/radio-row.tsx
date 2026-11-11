"use client";

import * as RadioGroup from "@radix-ui/react-radio-group";
import { useId, type ReactNode } from "react";

import { cn } from "./cn";
import type { AccessibleName } from "./field";

export type RadioRowGroupProps<T extends string> = AccessibleName & {
  value: T | undefined;
  onValueChange: (value: T) => void;
  children: ReactNode;
  className?: string;
};

/** Full-width options with explanations, e.g. the export scope (brandbook §6, FE-05). */
export function RadioRowGroup<T extends string>({
  value,
  onValueChange,
  children,
  className,
  label,
  ...name
}: RadioRowGroupProps<T>) {
  const labelId = useId();

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <span id={labelId} className="text-label text-text">
          {label}
        </span>
      )}
      <RadioGroup.Root
        value={value ?? ""}
        onValueChange={(next) => onValueChange(next as T)}
        aria-labelledby={label ? labelId : name["aria-labelledby"]}
        aria-label={name["aria-label"]}
        className="flex flex-col gap-2"
      >
        {children}
      </RadioGroup.Root>
    </div>
  );
}

export type RadioRowProps = {
  value: string;
  title: string;
  description?: string;
  disabled?: boolean;
};

/** The whole row is the `<label>`, so a click on the text selects it. */
export function RadioRow({ value, title, description, disabled }: RadioRowProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const descriptionId = `${id}-description`;

  return (
    <label
      className={cn(
        "border-border bg-surface flex cursor-pointer items-start gap-2.5 rounded-lg border p-3",
        "duration-fast transition-colors ease-out",
        "has-aria-checked:border-accent has-aria-checked:shadow-row-selected",
        "has-focus-visible:outline-focus has-focus-visible:outline-2 has-focus-visible:outline-offset-2",
        "has-disabled:cursor-not-allowed",
      )}
    >
      <RadioGroup.Item
        value={value}
        disabled={disabled}
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        className={cn(
          "border-control mt-0.5 grid size-4.5 shrink-0 place-items-center rounded-full border-2",
          "data-[state=checked]:border-accent focus-visible:outline-hidden",
          "disabled:border-border",
        )}
      >
        <RadioGroup.Indicator className="bg-accent size-2 rounded-full" />
      </RadioGroup.Item>
      <span className="flex min-w-0 flex-col gap-0.5">
        <span
          id={titleId}
          className={cn("text-body font-medium", disabled ? "text-text3" : "text-text")}
        >
          {title}
        </span>
        {description && (
          <span id={descriptionId} className="text-caption text-text3">
            {description}
          </span>
        )}
      </span>
    </label>
  );
}
