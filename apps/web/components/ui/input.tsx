"use client";

import type { ComponentPropsWithRef, ReactNode, Ref } from "react";

import { cn } from "./cn";
import { Field, fieldFrameClasses, useFieldIds, type FieldProps } from "./field";

export type InputProps = Omit<ComponentPropsWithRef<"input">, "className"> &
  FieldProps & {
    /** Inside the field on the left, e.g. a 16 px search icon. */
    leading?: ReactNode;
    /** Inside the field on the right, e.g. the `/` hotkey hint or a clear button. */
    trailing?: ReactNode;
    /** The bordered frame, for popovers that align with the whole field. */
    frameRef?: Ref<HTMLDivElement>;
    className?: string;
  };

export function Input({
  label,
  labelHidden,
  hint,
  error,
  counter,
  leading,
  trailing,
  frameRef,
  className,
  id,
  disabled,
  "aria-describedby": describedByProp,
  ...props
}: InputProps) {
  const { controlId, describedBy } = useFieldIds(id, { label, hint, error, counter });

  return (
    <div className={className}>
      <Field
        controlId={controlId}
        label={label}
        labelHidden={labelHidden}
        hint={hint}
        error={error}
        counter={counter}
      >
        <div
          ref={frameRef}
          className={cn(
            "h-control-md text-body flex items-center gap-2 px-3",
            fieldFrameClasses({ error, disabled }),
          )}
        >
          {leading}
          <input
            id={controlId}
            disabled={disabled}
            aria-invalid={error ? true : undefined}
            aria-describedby={cn(describedByProp, describedBy) || undefined}
            className="placeholder:text-text3 h-full min-w-0 flex-1 bg-transparent outline-hidden disabled:cursor-not-allowed"
            {...props}
          />
          {trailing}
        </div>
      </Field>
    </div>
  );
}
