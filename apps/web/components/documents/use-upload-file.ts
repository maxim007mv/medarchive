import { useCallback, useEffect, useReducer, useRef } from "react";

import { newIdempotencyKey } from "@/lib/api/client";
import { ApiError, NetworkError, type Problem } from "@/lib/api/errors";
import type { DocumentWithEtag } from "@/lib/api/queries";
import {
  checkPdfFile,
  createDocument,
  type DocumentCreate,
  postToStorage,
  requestUpload,
} from "@/lib/api/upload";

import {
  type FailureCode,
  initialUploadState,
  needsAnotherFile,
  uploadReducer,
} from "./upload-machine";

export type DocumentFields = Omit<DocumentCreate, "upload_id">;

/** Problems about what the person typed: they go under the fields, the upload stays. */
const FIELD_CODES = new Set<string>([
  "validation_error",
  "title_required",
  "title_too_long",
  "date_invalid",
  "date_in_future",
  "note_too_long",
  "type_unknown",
]);

function failureCode(error: unknown): FailureCode {
  if (error instanceof ApiError) return error.code;
  if (error instanceof NetworkError) return "network";
  return "internal";
}

type Options = {
  /** Read at the moment of saving, so the latest input goes to the server. */
  getFields: () => DocumentFields;
  onSaved: (saved: DocumentWithEtag) => void;
  onFieldErrors: (problem: Problem) => void;
};

/** Runs the upload of one file and the save of its document (FE-12) on top of `uploadReducer`. */
export function useUploadFile(file: File, options: Options) {
  const [state, dispatch] = useReducer(uploadReducer, initialUploadState);
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const abortRef = useRef<AbortController | null>(null);
  // One key per intention to save this upload; a new upload is a new intention.
  const documentKeyRef = useRef(newIdempotencyKey());

  const startUpload = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    dispatch({ type: "select" });

    const checkCode = await checkPdfFile(file);
    if (controller.signal.aborted) return;
    if (checkCode) {
      dispatch({ type: "failed", code: checkCode });
      return;
    }
    try {
      const upload = await requestUpload(file, newIdempotencyKey());
      if (controller.signal.aborted) return;
      dispatch({ type: "progress", percent: 0 });
      await postToStorage(
        upload,
        file,
        (percent) => dispatch({ type: "progress", percent }),
        controller.signal,
      );
      documentKeyRef.current = newIdempotencyKey();
      dispatch({ type: "uploaded", uploadId: upload.upload_id });
    } catch (error) {
      if (!controller.signal.aborted) dispatch({ type: "failed", code: failureCode(error) });
    }
  }, [file]);

  useEffect(() => {
    void startUpload();
    return () => abortRef.current?.abort();
  }, [startUpload]);

  const uploadId = state.phase.status === "saving" ? state.phase.uploadId : null;
  useEffect(() => {
    if (uploadId === null) return;
    // A repeated run (Strict Mode, retry) reuses the key, so the server answers with the same document.
    createDocument(
      { upload_id: uploadId, ...optionsRef.current.getFields() },
      documentKeyRef.current,
    )
      .then((saved) => {
        dispatch({ type: "saved", documentId: saved.document.id });
        optionsRef.current.onSaved(saved);
      })
      .catch((error: unknown) => {
        if (error instanceof ApiError && FIELD_CODES.has(error.code)) {
          optionsRef.current.onFieldErrors(error.problem);
          dispatch({ type: "fieldsRejected" });
          return;
        }
        if (error instanceof ApiError && error.code === "idempotency_key_reused") {
          documentKeyRef.current = newIdempotencyKey();
        }
        dispatch({ type: "failed", code: failureCode(error) });
      });
  }, [uploadId]);

  const retry = useCallback(() => {
    if (state.phase.status === "failed" && state.phase.uploadId !== null)
      dispatch({ type: "retrySave" });
    else void startUpload();
  }, [state.phase, startUpload]);

  /** «Сохранить» after a failure a retry can fix is also «Повторить»: the person asked for the outcome. */
  const save = useCallback(() => {
    dispatch({ type: "save" });
    if (state.phase.status === "failed" && !needsAnotherFile(state.phase.code)) retry();
  }, [state.phase, retry]);

  const cancel = useCallback(() => abortRef.current?.abort(), []);

  return { state, save, retry, cancel };
}
