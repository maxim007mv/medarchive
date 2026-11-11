"use client";

import { CircleCheck, FileText, RotateCw, Upload } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { cn } from "@/components/ui/cn";
import { Dialog } from "@/components/ui/dialog";
import { useIsOnline } from "@/lib/api/connectivity";
import type { DocumentWithEtag } from "@/lib/api/queries";
import { PDF_MIME } from "@/lib/api/upload";
import { type DateGuess, guessDocumentDate } from "@/lib/document-date";
import { formatDate, formatSize, titleFromFileName } from "@/lib/format";
import { errorTitles, t, texts } from "@/lib/texts";

import {
  applyProblemToForm,
  type DocumentForm,
  DocumentFields,
  toDocumentFields,
  useDocumentForm,
} from "./EditForm";
import { todayIso } from "./today";
import {
  type FailureCode,
  isSaveInProgress,
  needsAnotherFile,
  type UploadPhase,
} from "./upload-machine";
import { useUploadFile } from "./use-upload-file";

type Props = {
  /** Files chosen before opening; none opens the dialog idle, with its drop zone. */
  initialFiles: File[];
  onSaved: (saved: DocumentWithEtag) => void;
  onClose: () => void;
};

/** «Новый документ» (FE-12, D02..D05, M03): one file after another, «Файл 1 из 3». */
export function UploadDialog({ initialFiles, onSaved, onClose }: Props) {
  const [files, setFiles] = useState(initialFiles);
  const [index, setIndex] = useState(0);
  const [confirmClose, setConfirmClose] = useState(false);
  const hasInputRef = useRef(false);
  const file = files[index];

  function requestClose() {
    if (hasInputRef.current) setConfirmClose(true);
    else onClose();
  }

  return (
    <>
      <Dialog
        open
        onOpenChange={(open) => !open && requestClose()}
        title={texts["upload.title"]}
        description={texts["upload.subtitle"]}
      >
        {file ? (
          <UploadStep
            key={index}
            initialFile={file}
            position={files.length > 1 ? { n: index + 1, total: files.length } : null}
            onInputChange={(hasInput) => {
              hasInputRef.current = hasInput;
            }}
            onCancel={requestClose}
            onSaved={(saved) => {
              onSaved(saved);
              hasInputRef.current = false;
              if (index + 1 < files.length) setIndex(index + 1);
              else onClose();
            }}
          />
        ) : (
          <DropZone onFiles={setFiles} />
        )}
      </Dialog>
      <Dialog
        open={confirmClose}
        onOpenChange={setConfirmClose}
        width="confirm"
        title={texts["upload.closeConfirm.title"]}
        description={texts["upload.closeConfirm.text"]}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmClose(false)}>
              {texts["upload.closeConfirm.continue"]}
            </Button>
            <Button variant="danger" onClick={onClose}>
              {texts["upload.closeConfirm.close"]}
            </Button>
          </>
        }
      />
    </>
  );
}

/** Idle dialog (D04, top): drop files here or click to choose them. */
function DropZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [over, setOver] = useState(false);
  const pickerRef = useRef<HTMLInputElement>(null);

  function take(list: FileList | null) {
    const chosen = [...(list ?? [])];
    if (chosen.length > 0) onFiles(chosen);
  }

  return (
    <div className="pb-4 md:pb-6">
      <button
        type="button"
        onClick={() => pickerRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setOver(false);
          take(event.dataTransfer.files);
        }}
        className={cn(
          "duration-fast flex w-full flex-col items-center gap-2 rounded-xl border border-dashed p-8 text-center transition-colors",
          over ? "border-accent bg-accent-soft" : "border-control bg-surface hover:bg-sunken",
        )}
      >
        <Upload size={20} strokeWidth={1.75} className="text-accent" aria-hidden />
        <span className="text-label">
          {over ? texts["upload.dropOver"] : texts["onboarding.drop.text"]}
        </span>
        <span className="text-caption text-text3">{texts["onboarding.drop.limits"]}</span>
      </button>
      <input
        ref={pickerRef}
        type="file"
        accept={PDF_MIME}
        multiple
        hidden
        data-testid="upload-file-input"
        onChange={(event) => take(event.target.files)}
      />
    </div>
  );
}

const SHORT_FILE_STATUS: Partial<Record<FailureCode, string>> = {
  not_pdf: texts["upload.file.notPdf"],
  file_too_large: texts["upload.file.tooLarge"],
  pdf_unreadable: texts["upload.file.unreadable"],
  pdf_encrypted: texts["upload.file.encrypted"],
};

function UploadStep({
  initialFile,
  position,
  onInputChange,
  onCancel,
  onSaved,
}: {
  initialFile: File;
  position: { n: number; total: number } | null;
  onInputChange: (hasInput: boolean) => void;
  onCancel: () => void;
  onSaved: (saved: DocumentWithEtag) => void;
}) {
  const [file, setFile] = useState(initialFile);
  const [uploadedAt] = useState(() => new Date());
  const form = useDocumentForm({
    title: titleFromFileName(initialFile.name),
    type: undefined,
    date: "",
    undated: false,
  });
  const dateHint = useGuessedDate(file, form);
  const upload = useUploadFile(file, {
    getFields: () => toDocumentFields(form.getValues()),
    onSaved,
    onFieldErrors: (problem) => applyProblemToForm(form, problem),
  });
  const online = useIsOnline();
  const pickerRef = useRef<HTMLInputElement>(null);
  const reasonId = useId();
  const { isDirty } = form.formState;
  const titleEmpty = form.watch("title").trim() === "";
  const { phase } = upload.state;
  const fileProblem = phase.status === "failed" && needsAnotherFile(phase.code);

  useEffect(() => {
    onInputChange(isDirty);
  }, [isDirty, onInputChange]);

  function replaceFile(next: File | undefined) {
    if (!next) return;
    if (!form.getFieldState("title").isDirty) form.setValue("title", titleFromFileName(next.name));
    setFile(next);
  }

  const submit = form.handleSubmit(() => upload.save());
  const saveLabel =
    position && position.n < position.total ? texts["upload.queue.saveNext"] : texts["upload.save"];
  const disabledReason = !online
    ? texts["offline.disabledReason"]
    : titleEmpty
      ? texts["upload.save.disabledReason"]
      : undefined;

  return (
    <form
      noValidate
      onSubmit={(event) => void submit(event)}
      // Enter in a field asks to save even while the button is unavailable, so errors show (TC-012).
      onKeyDown={(event) => {
        if (event.key !== "Enter" || !(event.target instanceof HTMLInputElement)) return;
        event.preventDefault();
        if (!fileProblem) void submit();
      }}
      className="flex flex-col gap-4"
    >
      {position && <p className="text-label text-text2">{t("upload.queue.position", position)}</p>}
      <FileRow file={file} phase={phase} />
      <FileProblem
        phase={phase}
        onRetry={upload.retry}
        onPickOther={() => pickerRef.current?.click()}
      />
      <input
        ref={pickerRef}
        type="file"
        accept={PDF_MIME}
        hidden
        onChange={(event) => {
          replaceFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <DocumentFields form={form} uploadedAt={uploadedAt} dateHint={dateHint} />
      <div className="flex flex-col-reverse gap-2 pt-2 md:flex-row md:items-center md:justify-end">
        {disabledReason && (
          <p id={reasonId} className="text-caption text-text3 md:mr-auto">
            {disabledReason}
          </p>
        )}
        <Button variant="tertiary" onClick={onCancel} className="max-md:h-control-lg">
          {texts["common.cancel"]}
        </Button>
        <Button
          type="submit"
          loading={isSaveInProgress(upload.state)}
          loadingText={texts["upload.saving"]}
          disabled={Boolean(disabledReason) || fileProblem}
          aria-describedby={disabledReason ? reasonId : undefined}
          className="max-md:h-control-lg"
        >
          {saveLabel}
        </Button>
      </div>
    </form>
  );
}

const DATE_SOURCE_HINTS: Record<DateGuess["source"], string> = {
  fileName: texts["upload.date.fromFileName"],
  pdf: texts["upload.date.fromPdf"],
};

/**
 * Puts the date found in the chosen file into «Дата документа» (TC-118) and returns where it came
 * from while the field still holds it. A typed date and «Дата не указана» are left alone; a date
 * filled in for the previous file gives way to the new file's.
 */
function useGuessedDate(file: File, form: DocumentForm): string | undefined {
  const [guess, setGuess] = useState<{ text: string; source: DateGuess["source"] } | null>(null);
  const filledText = useRef<string | null>(null);

  useEffect(() => {
    let current = true;
    void guessDocumentDate(file, todayIso()).then((found) => {
      const { date, undated } = form.getValues();
      const ownDate = date !== "" && date !== filledText.current;
      if (!current || undated || ownDate) return;
      const text = found ? formatDate(found.date) : "";
      filledText.current = text;
      form.setValue("date", text);
      setGuess(found && { text, source: found.source });
    });
    return () => {
      current = false;
    };
  }, [file, form]);

  return guess && form.watch("date") === guess.text ? DATE_SOURCE_HINTS[guess.source] : undefined;
}

function FileRow({ file, phase }: { file: File; phase: UploadPhase }) {
  const size = formatSize(file.size);
  const percent =
    phase.status === "uploading" ? phase.percent : phase.status === "verifying" ? 100 : null;
  const shortStatus = phase.status === "failed" ? SHORT_FILE_STATUS[phase.code] : undefined;
  const ready = phase.status === "ready" || phase.status === "saving";

  return (
    <div className="border-border bg-surface flex items-start gap-3 rounded-lg border p-3">
      <span
        className="size-icon-button-sm bg-sunken text-text2 grid shrink-0 place-items-center rounded-md"
        aria-hidden
      >
        <FileText size={16} strokeWidth={1.75} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="text-body truncate font-medium">{file.name}</p>
        <p className="text-caption text-text3">
          {percent === null ? size : t("upload.file.progress", { size, n: percent })}
        </p>
        {shortStatus && <p className="text-caption text-danger">{shortStatus}</p>}
        {percent !== null && (
          <div
            role="progressbar"
            aria-valuenow={percent}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={file.name}
            className="bg-sunken h-1 overflow-hidden rounded-full"
          >
            <div
              className="bg-accent duration-base h-full transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>
        )}
      </div>
      {ready && (
        <span className="text-caption text-success flex shrink-0 items-center gap-1.5">
          <CircleCheck size={16} strokeWidth={1.75} aria-hidden />
          {texts["upload.file.ready"]}
        </span>
      )}
    </div>
  );
}

/** What went wrong and the one action that helps: another file, or a retry that keeps the input. */
function FileProblem({
  phase,
  onRetry,
  onPickOther,
}: {
  phase: UploadPhase;
  onRetry: () => void;
  onPickOther: () => void;
}) {
  if (phase.status !== "failed") return null;
  const { code } = phase;
  const isNetwork = code === "network";
  const title = isNetwork ? t("upload.network.title", { n: phase.percent }) : errorTitles[code];
  const otherFile = needsAnotherFile(code);
  // Expired or lost uploads are retried with the same file, which gets a new upload_id.
  const retryLabel =
    isNetwork || code === "upload_expired" || code === "upload_not_found"
      ? texts["upload.network.retry"]
      : texts["common.retry"];

  return (
    <Alert variant="danger" title={title}>
      <div className="flex flex-col gap-2">
        {isNetwork && <p>{texts["upload.network.text"]}</p>}
        <Button
          variant="secondary"
          size="sm"
          icon={otherFile ? undefined : RotateCw}
          onClick={otherFile ? onPickOther : onRetry}
          className="self-start"
        >
          {otherFile ? texts["upload.file.pickOther"] : retryLabel}
        </Button>
      </div>
    </Alert>
  );
}
