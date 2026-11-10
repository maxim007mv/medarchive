"use client";

import * as RadioGroup from "@radix-ui/react-radio-group";
import { TriangleAlert } from "lucide-react";
import { useId } from "react";

import { cn } from "./cn";
import type { AccessibleName } from "./field";

export type SegmentOption<T extends string> = { value: T; label: string };

export type SegmentedControlProps<T extends string> = AccessibleName & {
  /** 2 to 4 short options; more than that is not a segment (brandbook §6). */
  options: readonly SegmentOption<T>[];
  /** `undefined` selects nothing, e.g. the document type before the first choice. */
  value: T | undefined;
  onValueChange: (value: T) => void;
  /** Stretch to the container with equal segments, as in the upload form. */
  fullWidth?: boolean;
  disabled?: boolean;
  error?: string;
  className?: string;
};

/** Radix RadioGroup: arrow keys move and select, Tab enters at the selected segment (FE-05). */
export function SegmentedControl<T extends string>({
  options,
  value,
  onValueChange,
  fullWidth = false,
  disabled,
  error,
  className,
  label,
  ...name
}: SegmentedControlProps<T>) {
  const id = useId();
  const labelId = `${id}-label`;
  const errorId = `${id}-error`;

  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <span id={labelId} className="text-label text-text">
          {label}
        </span>
      )}
      <RadioGroup.Root
        // "" matches no option: controlled, with nothing selected.
        value={value ?? ""}
        onValueChange={(next) => onValueChange(next as T)}
        orientation="horizontal"
        disabled={disabled}
        aria-labelledby={label ? labelId : name["aria-labelledby"]}
        aria-label={name["aria-label"]}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        className={cn(
          "bg-sunken gap-0.5 rounded-md p-1",
          fullWidth ? "flex w-full" : "inline-flex self-start",
        )}
      >
        {options.map((option) => (
          <RadioGroup.Item
            key={option.value}
            value={option.value}
            className={cn(
              "h-control-sm text-label text-text2 rounded-sm px-3 whitespace-nowrap",
              "duration-fast hover:text-text transition-colors ease-out",
              "data-[state=checked]:bg-surface data-[state=checked]:text-text data-[state=checked]:shadow-segment",
              "disabled:text-disabled-text disabled:cursor-not-allowed",
              fullWidth && "flex-1",
            )}
          >
            {option.label}
          </RadioGroup.Item>
        ))}
      </RadioGroup.Root>
      {error && (
        <p id={errorId} role="alert" className="text-caption text-danger flex items-start gap-1.5">
          <TriangleAlert size={16} strokeWidth={1.75} className="shrink-0" aria-hidden />
          {error}
        </p>
      )}
    </div>
  );
}
