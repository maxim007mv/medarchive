"use client";

import { useQueryClient } from "@tanstack/react-query";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ApiError, isApiError } from "@/lib/api/errors";
import { type DocumentWithEtag, queryKeys, useUpdateDocument } from "@/lib/api/queries";
import { errorTitles, texts } from "@/lib/texts";

import {
  applyProblemToForm,
  DocumentFields,
  formDefaults,
  toDocumentFields,
  useDocumentForm,
} from "./EditForm";
import { useProblem } from "./use-problem";

/**
 * D10 «Изменить описание» (FE-17): the upload form fields, saved with `If-Match`. On 412 the typed
 * values stay in the fields and «Обновить» loads the current version to save over it.
 */
export function EditPanel({
  current,
  onDone,
  disabledReason,
}: {
  current: DocumentWithEtag;
  onDone: () => void;
  disabledReason?: string;
}) {
  const queryClient = useQueryClient();
  const form = useDocumentForm(formDefaults(current.document));
  const update = useUpdateDocument(current.document.id);
  const conflict = isApiError(update.error, "version_conflict");
  const otherProblem = useProblem(
    update.error instanceof ApiError && !conflict ? update.error : null,
  );

  const submit = form.handleSubmit((values) =>
    update.mutate(
      { etag: current.etag, patch: toDocumentFields(values) },
      {
        onSuccess: onDone,
        onError: (error) => {
          if (error instanceof ApiError && error.status === 422)
            applyProblemToForm(form, error.problem);
        },
      },
    ),
  );

  async function refresh() {
    await queryClient.refetchQueries({
      queryKey: queryKeys.document(current.document.id),
      exact: true,
    });
    update.reset();
  }

  return (
    <form noValidate onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
      {conflict && (
        <Alert
          variant="danger"
          title={errorTitles.version_conflict}
          action={
            <Button variant="secondary" size="sm" onClick={() => void refresh()}>
              {texts["edit.conflict.refresh"]}
            </Button>
          }
        />
      )}
      {otherProblem && update.error instanceof ApiError && update.error.status !== 422 && (
        <Alert variant="danger" title={otherProblem.title} />
      )}
      <DocumentFields form={form} />
      <div className="flex justify-end gap-2">
        <Button variant="tertiary" onClick={onDone}>
          {texts["edit.cancel"]}
        </Button>
        <Button
          type="submit"
          loading={update.isPending}
          disabled={Boolean(disabledReason)}
          disabledReason={disabledReason}
        >
          {texts["edit.save"]}
        </Button>
      </div>
    </form>
  );
}
