"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { isApiError } from "@/lib/api/errors";
import { queryKeys, useDeleteDocument } from "@/lib/api/queries";
import { formatDate } from "@/lib/format";
import { t, texts } from "@/lib/texts";

import { useProblem } from "./use-problem";

export type DeleteTarget = { id: string; title: string; document_date: string | null };

/**
 * D11 / M07: «Удалить документ?» with the title and date. Focus starts on «Отмена», so Enter
 * closes the dialog and deletes nothing (TC-060).
 */
export function DeleteDialog({
  target,
  getEtag,
  returnFocusTo,
  onClose,
  onDeleted,
}: {
  target: DeleteTarget;
  /** `If-Match` of the document: from the open card, or loaded for a list row. */
  getEtag: () => Promise<string>;
  /** Focused again after Esc or «Отмена» (TC-056). */
  returnFocusTo: HTMLElement | null;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  function close() {
    onClose();
    // Radix returns focus only to its own Dialog.Trigger; this dialog is opened by a row menu or a
    // panel button. Its focus scope settles on the next task, so the hand-back waits for it.
    setTimeout(() => returnFocusTo?.focus(), 0);
  }
  const showToast = useToast();
  const queryClient = useQueryClient();
  const deletion = useDeleteDocument();
  const problem = useProblem(deletion.error);
  const date = target.document_date ? formatDate(target.document_date) : null;

  async function confirm() {
    try {
      await deletion.mutateAsync({ id: target.id, etag: await getEtag() });
    } catch (error) {
      // Already gone in another tab: the person wanted exactly this outcome.
      if (!isApiError(error, "not_found")) return;
      queryClient.removeQueries({ queryKey: queryKeys.document(target.id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.allDocuments });
    }
    showToast({ title: texts["delete.toast"] });
    onDeleted();
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && close()}
      width="confirm"
      initialFocus={cancelRef}
      title={texts["delete.title"]}
      description={
        <>
          <span className="hidden md:inline">
            {date
              ? t("delete.text", { title: target.title, date })
              : t("delete.text.undated", { title: target.title })}
          </span>
          <span className="md:hidden">
            {date
              ? t("delete.text.mobile", { title: target.title, date })
              : t("delete.text.mobile.undated", { title: target.title })}
          </span>
        </>
      }
      footer={
        <>
          <Button ref={cancelRef} variant="secondary" onClick={close}>
            {texts["delete.cancel"]}
          </Button>
          <Button variant="danger" loading={deletion.isPending} onClick={() => void confirm()}>
            {texts["delete.confirm"]}
          </Button>
        </>
      }
    >
      {problem && <Alert variant="danger" title={problem.title} />}
    </Dialog>
  );
}
