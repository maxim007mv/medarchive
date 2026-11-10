"use client";

import { Check, LoaderCircle } from "lucide-react";
import { useId } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { errorTitles, t, texts } from "@/lib/texts";

import { NOTE_MAX_CHARS, type NoteStatus, useNoteAutosave } from "./use-note-autosave";

export const NOTE_UNDO_MS = 6000;

/** «Не сохранилось. Повторить»: the dictionary keeps one sentence, its last word is the button. */
function splitFailed(): [string, string] {
  const words = texts["note.failed"].split(" ");
  return [words.slice(0, -1).join(" "), words.at(-1) ?? ""];
}

function StatusLine({ status, onRetry }: { status: NoteStatus; onRetry: () => void }) {
  if (status === "saving") {
    return (
      <span className="text-text3 inline-flex items-center gap-1.5">
        <LoaderCircle
          size={14}
          strokeWidth={1.75}
          className="motion-safe:animate-spin"
          aria-hidden
        />
        {texts["note.saving"]}
      </span>
    );
  }
  if (status === "saved") {
    return (
      <span className="text-success inline-flex items-center gap-1.5">
        <Check size={14} strokeWidth={1.75} aria-hidden />
        {texts["note.saved"]}
      </span>
    );
  }
  if (status === "failed") {
    const [text, action] = splitFailed();
    return (
      <span className="text-danger">
        {text}{" "}
        <button type="button" onClick={onRetry} className="rounded-xs font-medium underline">
          {action}
        </button>
      </span>
    );
  }
  if (status === "tooLong")
    return <span className="text-danger">{texts["note.tooLong.blocked"]}</span>;
  return null;
}

/** D09 note (FE-18): autosave, status next to the heading, «Очистить» with undo instead of a question. */
export function NotePanel({
  documentId,
  disabledReason,
}: {
  documentId: string;
  disabledReason?: string;
}) {
  const note = useNoteAutosave(documentId);
  const showToast = useToast();
  const headingId = useId();

  function clear() {
    const previous = note.draft;
    note.replace("");
    showToast({
      title: texts["note.cleared"],
      durationMs: NOTE_UNDO_MS,
      action: { label: texts["note.undo"], onClick: () => note.replace(previous) },
    });
  }

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id={headingId} className="text-h3">
          {texts["note.label"]}
        </h2>
        <p role="status" aria-live="polite" className="text-caption">
          <StatusLine status={note.status} onRetry={note.retry} />
        </p>
      </div>
      {note.status === "conflict" && (
        <Alert
          variant="danger"
          title={errorTitles.version_conflict}
          action={
            <Button variant="secondary" size="sm" onClick={() => void note.resolveConflict()}>
              {texts["edit.conflict.refresh"]}
            </Button>
          }
        />
      )}
      <Textarea
        label={texts["note.label"]}
        labelHidden
        placeholder={texts["note.placeholder"]}
        value={note.draft}
        onChange={(event) => note.setDraft(event.target.value)}
        error={note.draft.length > NOTE_MAX_CHARS ? errorTitles.note_too_long : undefined}
        counter={(n) => t("note.counter", { n })}
        readOnly={Boolean(disabledReason)}
      />
      <Button
        variant="tertiary"
        size="sm"
        onClick={clear}
        disabled={note.draft === "" || Boolean(disabledReason)}
        disabledReason={disabledReason}
        className="self-end"
      >
        {texts["note.clear"]}
      </Button>
    </section>
  );
}
