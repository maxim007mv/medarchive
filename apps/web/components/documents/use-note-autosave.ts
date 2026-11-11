import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, csrfHeaderSync, request } from "@/lib/api/client";
import { isApiError } from "@/lib/api/errors";
import { type DocumentWithEtag, patchDocument, queryKeys, storeDocument } from "@/lib/api/queries";

export const NOTE_MAX_CHARS = 2000;
export const NOTE_SAVE_DELAY_MS = 800;

export type NoteStatus = "idle" | "saving" | "saved" | "failed" | "conflict" | "tooLong";

const storageKey = (documentId: string) => `medarchive:note:${documentId}`;

function readCopy(documentId: string): string | null {
  return sessionStorage.getItem(storageKey(documentId));
}

/**
 * Note of a document with autosave (FE-18): 800 ms after the last keystroke, optimistic in the cache
 * with rollback on error, one request at a time (each needs the ETag of the previous one), a copy in
 * sessionStorage until the server confirms, and a `keepalive` request when the page is hidden.
 */
export function useNoteAutosave(documentId: string) {
  const queryClient = useQueryClient();
  const key = useMemo(() => queryKeys.document(documentId), [documentId]);
  const cached = useCallback(
    () => queryClient.getQueryData<DocumentWithEtag>(key),
    [queryClient, key],
  );

  const serverNote = cached()?.document.note ?? "";
  const [draft, setDraftState] = useState(() => readCopy(documentId) ?? serverNote);
  const [status, setStatus] = useState<NoteStatus>(() =>
    draft !== serverNote ? "idle" : serverNote ? "saved" : "idle",
  );

  const draftRef = useRef(draft);
  const savedRef = useRef(serverNote);
  const inFlightRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const { mutateAsync } = useMutation({
    mutationFn: ({ note, etag }: { note: string; etag: string }) =>
      patchDocument(documentId, etag, { note: note === "" ? null : note }),
    onMutate: async ({ note }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = cached();
      if (previous) {
        queryClient.setQueryData<DocumentWithEtag>(key, {
          ...previous,
          document: { ...previous.document, note: note === "" ? null : note },
        });
      }
      return { previous };
    },
    onError: (_error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(key, context.previous);
    },
    onSuccess: (saved) => storeDocument(queryClient, saved),
  });

  const save = useCallback(
    async (note: string) => {
      if (note.length > NOTE_MAX_CHARS) return;
      if (inFlightRef.current) return;
      const etag = cached()?.etag;
      if (etag === undefined) return;
      inFlightRef.current = true;
      setStatus("saving");
      try {
        await mutateAsync({ note, etag });
        savedRef.current = note;
        if (draftRef.current === note) {
          sessionStorage.removeItem(storageKey(documentId));
          setStatus("saved");
        }
      } catch (error) {
        setStatus(isApiError(error, "version_conflict") ? "conflict" : "failed");
        return;
      } finally {
        inFlightRef.current = false;
      }
      // Typed while the request was on its way: save the newer text with the new ETag.
      if (draftRef.current !== note) void save(draftRef.current);
    },
    [cached, documentId, mutateAsync],
  );

  const cancelTimer = useCallback(() => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const setDraft = useCallback(
    (note: string) => {
      draftRef.current = note;
      setDraftState(note);
      cancelTimer();
      if (note === savedRef.current) {
        sessionStorage.removeItem(storageKey(documentId));
      } else {
        sessionStorage.setItem(storageKey(documentId), note);
      }
      if (note.length > NOTE_MAX_CHARS) {
        setStatus("tooLong");
        return;
      }
      if (inFlightRef.current) return;
      setStatus(note === savedRef.current ? (note ? "saved" : "idle") : "idle");
      timerRef.current = setTimeout(() => void save(note), NOTE_SAVE_DELAY_MS);
    },
    [documentId, save, cancelTimer],
  );

  /** Sets the text and saves it at once: «Очистить» and «Вернуть» are deliberate actions. */
  const replace = useCallback(
    (note: string) => {
      setDraft(note);
      cancelTimer();
      void save(note);
    },
    [setDraft, save, cancelTimer],
  );

  const retry = useCallback(() => void save(draftRef.current), [save]);

  /** After `version_conflict`: take the current version, keep the typed text and save it over it. */
  const resolveConflict = useCallback(async () => {
    await queryClient.refetchQueries({ queryKey: key, exact: true });
    savedRef.current = cached()?.document.note ?? "";
    void save(draftRef.current);
  }, [queryClient, key, cached, save]);

  useEffect(() => {
    const flush = () => {
      const note = draftRef.current;
      const etag = cached()?.etag;
      const csrf = csrfHeaderSync();
      if (note === savedRef.current || note.length > NOTE_MAX_CHARS || inFlightRef.current) return;
      if (!etag || !csrf) return;
      cancelTimer();
      inFlightRef.current = true;
      // Sent without awaiting anything first: the page may be gone right after this handler.
      request(
        api.PATCH("/api/v1/documents/{document_id}", {
          params: { path: { document_id: documentId }, header: { "If-Match": etag, ...csrf } },
          body: { note: note === "" ? null : note },
          keepalive: true,
        }),
      )
        .then(({ data, response }) => {
          savedRef.current = note;
          storeDocument(queryClient, { document: data, etag: response.headers.get("ETag") ?? "" });
          if (draftRef.current === note) {
            sessionStorage.removeItem(storageKey(documentId));
            setStatus("saved");
          }
        })
        .catch(() => setStatus("failed"))
        .finally(() => {
          inFlightRef.current = false;
        });
    };
    const onVisibility = () => {
      if (document.visibilityState === "hidden") flush();
    };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("beforeunload", flush);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("beforeunload", flush);
    };
  }, [cached, cancelTimer, documentId, queryClient]);

  // A copy left by an earlier visit that the server never confirmed goes out as a normal save.
  useEffect(() => {
    if (draftRef.current !== savedRef.current) {
      timerRef.current = setTimeout(() => void save(draftRef.current), NOTE_SAVE_DELAY_MS);
    }
    return cancelTimer;
  }, [save, cancelTimer]);

  return { draft, status, setDraft, replace, retry, resolveConflict };
}
