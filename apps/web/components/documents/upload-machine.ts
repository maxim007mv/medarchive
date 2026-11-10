import type { ProblemCode } from "@/lib/api/errors";
import type { FileCheckCode } from "@/lib/api/upload";

/**
 * One file of UploadDialog (FE-12):
 * idle → selected (client check) → uploading(p) → verifying (all bytes sent, storage has not answered)
 * → ready → saving → saved, or failed(code) from any step before `saved`.
 * Saving can be asked for while the file is still on its way: it starts as soon as the upload is ready.
 */
export type FailureCode = FileCheckCode | ProblemCode | "network";

export type UploadPhase =
  | { status: "idle" }
  | { status: "selected" }
  | { status: "uploading"; percent: number }
  | { status: "verifying" }
  | { status: "ready"; uploadId: string }
  | { status: "saving"; uploadId: string }
  | { status: "saved"; documentId: string }
  | { status: "failed"; code: FailureCode; percent: number; uploadId: string | null };

export type UploadState = { phase: UploadPhase; saveRequested: boolean };

export type UploadEvent =
  | { type: "select" }
  | { type: "progress"; percent: number }
  | { type: "uploaded"; uploadId: string }
  | { type: "failed"; code: FailureCode }
  | { type: "save" }
  | { type: "retrySave" }
  | { type: "fieldsRejected" }
  | { type: "saved"; documentId: string };

export const initialUploadState: UploadState = { phase: { status: "idle" }, saveRequested: false };

/** Codes that need another file: retrying the same bytes cannot help. */
const FILE_CODES = new Set<FailureCode>([
  "not_pdf",
  "file_too_large",
  "pdf_unreadable",
  "pdf_encrypted",
]);

/** Codes after which the stored upload is gone, so «Повторить загрузку» needs a new `upload_id`. */
const UPLOAD_GONE_CODES = new Set<FailureCode>(["upload_not_found", "upload_expired"]);

export function needsAnotherFile(code: FailureCode): boolean {
  return FILE_CODES.has(code);
}

function percentOf(phase: UploadPhase): number {
  if (phase.status === "uploading") return phase.percent;
  if (phase.status === "failed") return phase.percent;
  return phase.status === "verifying" || phase.status === "ready" || phase.status === "saving"
    ? 100
    : 0;
}

function uploadIdOf(phase: UploadPhase): string | null {
  return phase.status === "ready" || phase.status === "saving" ? phase.uploadId : null;
}

export function uploadReducer(state: UploadState, event: UploadEvent): UploadState {
  const { phase } = state;
  switch (event.type) {
    case "select":
      return { phase: { status: "selected" }, saveRequested: state.saveRequested };
    case "progress":
      if (phase.status !== "selected" && phase.status !== "uploading") return state;
      return {
        ...state,
        phase:
          event.percent >= 100
            ? { status: "verifying" }
            : { status: "uploading", percent: event.percent },
      };
    case "uploaded":
      if (phase.status !== "verifying" && phase.status !== "uploading") return state;
      return {
        phase: { status: state.saveRequested ? "saving" : "ready", uploadId: event.uploadId },
        saveRequested: false,
      };
    case "save":
      if (phase.status === "ready")
        return { phase: { status: "saving", uploadId: phase.uploadId }, saveRequested: false };
      if (
        phase.status === "selected" ||
        phase.status === "uploading" ||
        phase.status === "verifying"
      ) {
        return { ...state, saveRequested: true };
      }
      // After a failure that a retry can fix the click is kept: the retry finishes with saving.
      if (phase.status === "failed" && !FILE_CODES.has(phase.code)) {
        return { ...state, saveRequested: true };
      }
      return state;
    case "fieldsRejected":
      if (phase.status !== "saving") return state;
      return { phase: { status: "ready", uploadId: phase.uploadId }, saveRequested: false };
    case "failed": {
      if (phase.status === "saved" || phase.status === "idle") return state;
      const isFileProblem = FILE_CODES.has(event.code);
      const keepsUpload = !isFileProblem && !UPLOAD_GONE_CODES.has(event.code);
      return {
        phase: {
          status: "failed",
          code: event.code,
          percent: percentOf(phase),
          uploadId: keepsUpload ? uploadIdOf(phase) : null,
        },
        // A retry finishes what the person already asked for, without pressing «Сохранить» again.
        saveRequested: !isFileProblem && (state.saveRequested || phase.status === "saving"),
      };
    }
    case "retrySave":
      if (phase.status !== "failed" || phase.uploadId === null) return state;
      return { phase: { status: "saving", uploadId: phase.uploadId }, saveRequested: false };
    case "saved":
      if (phase.status !== "saving") return state;
      return { phase: { status: "saved", documentId: event.documentId }, saveRequested: false };
  }
}

/** Shows «Сохраняем…» on the main button: saving runs or waits for the upload. */
export function isSaveInProgress(state: UploadState): boolean {
  return state.phase.status === "saving" || state.saveRequested;
}
