"use client";

import { useState, type ChangeEvent, type ComponentPropsWithRef } from "react";

import { cn } from "./cn";
import { Field, fieldFrameClasses, useFieldIds, type FieldProps } from "./field";

export type TextareaProps = Omit<ComponentPropsWithRef<"textarea">, "className"> &
  Omit<FieldProps, "counter"> & {
    /** Text under the field from the current length, e.g. `n => t("note.counter", { n })`. */
    counter?: (length: number) => string;
    className?: string;
  };

export function Textarea({
  label,
  labelHidden,
  hint,
  error,
  counter,
  className,
  id,
  disabled,
  value,
  defaultValue,
  onChange,
  "aria-describedby": describedByProp,
  ...props
}: TextareaProps) {
  // Counted on input as well, so the counter also works for uncontrolled fields.
  const [typedLength, setTypedLength] = useState(String(defaultValue ?? "").length);
  const length = value === undefined ? typedLength : String(value).length;
  const counterText = counter?.(length);
  const { controlId, describedBy } = useFieldIds(id, {
    label,
    hint,
    error,
    counter: counterText,
  });

  function handleChange(event: ChangeEvent<HTMLTextAreaElement>) {
    setTypedLength(event.target.value.length);
    onChange?.(event);
  }

  return (
    <div className={className}>
      <Field
        controlId={controlId}
        label={label}
        labelHidden={labelHidden}
        hint={hint}
        error={error}
        counter={counterText}
      >
        <textarea
          id={controlId}
          disabled={disabled}
          value={value}
          defaultValue={defaultValue}
          onChange={handleChange}
          aria-invalid={error ? true : undefined}
          aria-describedby={cn(describedByProp, describedBy) || undefined}
          className={cn(
            "text-body placeholder:text-text3 block min-h-30 w-full resize-y px-3 py-2.5 outline-hidden",
            fieldFrameClasses({ error, disabled }),
          )}
          {...props}
        />
      </Field>
    </div>
  );
}
