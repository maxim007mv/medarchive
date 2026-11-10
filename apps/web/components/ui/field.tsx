import { TriangleAlert } from "lucide-react";
import { useId, type ReactNode } from "react";

import { cn } from "./cn";

/** A visible label, or a name for controls whose label lives elsewhere (dialog title, cell). */
export type AccessibleName =
  | { label: string; "aria-label"?: undefined; "aria-labelledby"?: undefined }
  | { label?: undefined; "aria-label": string; "aria-labelledby"?: undefined }
  | { label?: undefined; "aria-label"?: undefined; "aria-labelledby": string };

/** Label above, hint or error below (brandbook §6). */
export type FieldProps = {
  label: string;
  /** For fields whose purpose is clear from the layout, e.g. search with a placeholder. */
  labelHidden?: boolean;
  hint?: ReactNode;
  /** Shown instead of the hint; marks the control `aria-invalid`. */
  error?: string;
  /** Right-aligned under the control, e.g. `12 / 2000`. */
  counter?: string;
};

export function useFieldIds(id: string | undefined, { hint, error, counter }: FieldProps) {
  const fallbackId = useId();
  const controlId = id ?? fallbackId;
  const describedBy = cn(
    error ? `${controlId}-error` : hint ? `${controlId}-hint` : null,
    counter && `${controlId}-counter`,
  );
  return { controlId, describedBy: describedBy || undefined };
}

/** Border, background and focus ring of a text control or of the frame around one. */
export function fieldFrameClasses({ error, disabled }: { error?: string; disabled?: boolean }) {
  return cn(
    "rounded-md border transition duration-fast ease-out",
    disabled ? "cursor-not-allowed border-border bg-sunken text-text3" : "bg-surface text-text",
    !disabled &&
      (error
        ? "border-danger shadow-field-error"
        : "border-control focus-within:border-focus focus-within:shadow-field-focus"),
  );
}

export function Field({
  controlId,
  label,
  labelHidden,
  hint,
  error,
  counter,
  children,
}: FieldProps & { controlId: string; children: ReactNode }) {
  const hasFooter = Boolean(error || hint || counter);

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={controlId} className={cn("text-label text-text", labelHidden && "sr-only")}>
        {label}
      </label>
      {children}
      {hasFooter && (
        <div className="text-caption flex items-start justify-between gap-3">
          {error ? (
            <p
              id={`${controlId}-error`}
              role="alert"
              className="text-danger flex items-start gap-1.5"
            >
              <TriangleAlert size={16} strokeWidth={1.75} className="shrink-0" aria-hidden />
              {error}
            </p>
          ) : (
            hint && (
              <p id={`${controlId}-hint`} className="text-text3">
                {hint}
              </p>
            )
          )}
          {counter && (
            <p id={`${controlId}-counter`} className="text-text3 ml-auto shrink-0 tabular-nums">
              {counter}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
