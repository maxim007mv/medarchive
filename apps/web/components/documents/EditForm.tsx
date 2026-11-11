"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm, type UseFormReturn } from "react-hook-form";
import { z } from "zod";

import { Alert } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { DateInput } from "@/components/ui/date-input";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { type Problem, pointerToField } from "@/lib/api/errors";
import { browserTimeZone } from "@/lib/api/queries";
import { DOCUMENT_TYPES } from "@/lib/filters";
import { formatDate, formatDateTime, parseDate } from "@/lib/format";
import { errorTitles, t, texts } from "@/lib/texts";

import { typeLabel } from "./list-texts";
import { todayIso } from "./today";

export const TITLE_MAX_CHARS = 200;
/** The counter appears near the limit (11-design-rationale, «Ввести название»). */
const TITLE_COUNTER_FROM = 180;
/** `дд.мм.гггг` */
const DATE_TEXT_LENGTH = 10;

const schema = z
  .object({
    title: z
      .string()
      .refine((value) => value.trim().length > 0, errorTitles.title_required)
      .refine((value) => value.trim().length <= TITLE_MAX_CHARS, errorTitles.title_too_long),
    type: z.enum(DOCUMENT_TYPES).optional(),
    date: z.string(),
    undated: z.boolean(),
  })
  .superRefine((values, context) => {
    if (values.type === undefined)
      context.addIssue({ code: "custom", path: ["type"], message: errorTitles.type_unknown });
    if (values.undated) return;
    const iso = parseDate(values.date);
    if (iso === null)
      context.addIssue({ code: "custom", path: ["date"], message: errorTitles.date_invalid });
    else if (iso > todayIso())
      context.addIssue({ code: "custom", path: ["date"], message: errorTitles.date_in_future });
  });

export type DocumentFormValues = z.input<typeof schema>;
export type DocumentForm = UseFormReturn<DocumentFormValues>;

export function useDocumentForm(defaults: DocumentFormValues): DocumentForm {
  return useForm<DocumentFormValues>({ resolver: zodResolver(schema), defaultValues: defaults });
}

export function formDefaults(document?: {
  title: string;
  type: DocumentFormValues["type"];
  document_date: string | null;
}): DocumentFormValues {
  if (!document) return { title: "", type: undefined, date: "", undated: false };
  return {
    title: document.title,
    type: document.type,
    date: document.document_date ? formatDate(document.document_date) : "",
    undated: document.document_date === null,
  };
}

/** Body fields of `POST`/`PATCH /api/v1/documents` from valid form values. */
export function toDocumentFields(values: DocumentFormValues) {
  return {
    title: values.title.trim(),
    type: values.type ?? "other",
    document_date: values.undated ? null : parseDate(values.date),
  };
}

const API_FIELDS: Record<string, keyof DocumentFormValues> = {
  title: "title",
  type: "type",
  document_date: "date",
};

/** Problem `errors[].pointer` → messages under the fields; a bare field code goes to its field. */
export function applyProblemToForm(form: DocumentForm, problem: Problem): void {
  const byCode: Record<string, keyof DocumentFormValues> = {
    title_required: "title",
    title_too_long: "title",
    type_unknown: "type",
    date_invalid: "date",
    date_in_future: "date",
  };
  const fieldErrors = problem.errors?.length
    ? problem.errors.map((error) => ({
        field: API_FIELDS[pointerToField(error.pointer)],
        title: error.title,
      }))
    : [{ field: byCode[problem.code], title: problem.title }];
  let focused = false;
  for (const { field, title } of fieldErrors) {
    if (!field) continue;
    form.setError(field, { message: title }, { shouldFocus: !focused });
    focused = true;
  }
}

const TYPE_OPTIONS = DOCUMENT_TYPES.map((type) => ({ value: type, label: typeLabel(type) }));

/**
 * Title, type, document date and «Дата не указана в документе» (D02, D03, D10). One component
 * for adding and editing; the parent owns the `<form>` and the buttons.
 */
export function DocumentFields({
  form,
  uploadedAt,
  disabled,
}: {
  form: DocumentForm;
  /** Shown in the hint «Дата загрузки запишется автоматически» when adding. */
  uploadedAt?: Date;
  disabled?: boolean;
}) {
  const { register, control, watch, formState } = form;
  const title = watch("title");
  const undated = watch("undated");
  const [uploadedDate, uploadedTime] = uploadedAt
    ? formatDateTime(uploadedAt, browserTimeZone()).split(", ")
    : [];

  return (
    <>
      <Input
        label={texts["upload.name.label"]}
        hint={texts["upload.name.hint"]}
        placeholder={texts["upload.name.placeholder"]}
        error={formState.errors.title?.message}
        counter={
          title.length >= TITLE_COUNTER_FROM
            ? t("upload.name.counter", { n: title.length })
            : undefined
        }
        disabled={disabled}
        autoComplete="off"
        {...register("title")}
      />
      <Controller
        control={control}
        name="type"
        render={({ field, fieldState }) => (
          <SegmentedControl
            label={texts["upload.type.label"]}
            options={TYPE_OPTIONS}
            value={field.value}
            onValueChange={field.onChange}
            error={fieldState.error?.message}
            disabled={disabled}
            fullWidth
          />
        )}
      />
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-end gap-4">
          <Controller
            control={control}
            name="date"
            render={({ field, fieldState }) => (
              <DateInput
                ref={field.ref}
                label={texts["upload.date.label"]}
                value={undated ? texts["upload.date.noneValue"] : field.value}
                // A half-typed date is not an error yet; a whole one is checked at once (TC-119).
                onChange={(value) => {
                  const complete = value.length === DATE_TEXT_LENGTH;
                  form.setValue("date", value, { shouldDirty: true, shouldValidate: complete });
                  if (!complete) form.clearErrors("date");
                }}
                onBlur={field.onBlur}
                max={todayIso()}
                disabled={disabled || undated}
                error={undated ? undefined : fieldState.error?.message}
                className="w-48"
              />
            )}
          />
          <Controller
            control={control}
            name="undated"
            render={({ field }) => (
              <Checkbox
                label={texts["upload.date.none"]}
                checked={field.value}
                onCheckedChange={(checked) => {
                  field.onChange(checked === true);
                  form.clearErrors("date");
                }}
                disabled={disabled}
                className="h-control-md"
              />
            )}
          />
        </div>
        {undated ? (
          <Alert variant="warn">{texts["upload.date.noneHint"]}</Alert>
        ) : (
          uploadedDate && (
            <p className="text-caption text-text3">
              {t("upload.uploadedAtHint", { date: uploadedDate, time: uploadedTime ?? "" })}
            </p>
          )
        )}
      </div>
    </>
  );
}
