import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type QueryClient,
} from "@tanstack/react-query";
import { useEffect } from "react";

import { type DocumentFilters, toListQuery } from "@/lib/filters";

import { api, call, csrfHeader, newIdempotencyKey, request, setCsrfToken } from "./client";
import { isApiError } from "./errors";
import type { components } from "./schema";

type Schemas = components["schemas"];
export type Session = Schemas["Session"];
export type Workspace = Schemas["Workspace"];
export type DocumentItem = Schemas["DocumentListItem"];
export type DocumentList = Schemas["DocumentList"];
export type DocumentFull = Schemas["Document"];
export type DocumentPatch = Schemas["DocumentPatch"];
export type ExportCreate = Schemas["ExportCreate"];

/** The list renders up to this many rows per request; larger archives load the next pages in turn. */
const LIST_PAGE_SIZE = 200;

export const queryKeys = {
  session: ["session"] as const,
  workspace: ["workspace"] as const,
  documents: (filters: DocumentFilters) => ["documents", filters] as const,
  documentCount: (filters: DocumentFilters) => ["documents", filters, "count"] as const,
  allDocuments: ["documents"] as const,
  document: (id: string) => ["document", id] as const,
};

export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** Current session or `null` when this browser has no archive (401 `unauthenticated`). */
export function useSession() {
  return useQuery({
    queryKey: queryKeys.session,
    queryFn: async (): Promise<Session | null> => {
      try {
        const session = await call(api.GET("/api/v1/session"));
        setCsrfToken(session.csrf_token);
        return session;
      } catch (error) {
        if (isApiError(error, "unauthenticated")) {
          setCsrfToken(null);
          return null;
        }
        throw error;
      }
    },
    staleTime: Infinity,
  });
}

async function fetchWorkspace() {
  const { data, response } = await request(api.GET("/api/v1/workspace"));
  return { workspace: data, etag: response.headers.get("ETag") ?? "" };
}

export function useWorkspace({ enabled }: { enabled: boolean }) {
  return useQuery({ queryKey: queryKeys.workspace, queryFn: fetchWorkspace, enabled });
}

/** All pages of the list for the filters (FE-13); following pages are fetched right after the first. */
export function useDocuments(filters: DocumentFilters, { enabled }: { enabled: boolean }) {
  const query = useInfiniteQuery({
    queryKey: queryKeys.documents(filters),
    queryFn: ({ pageParam }) =>
      call(
        api.GET("/api/v1/documents", {
          params: {
            query: {
              ...toListQuery(filters, browserTimeZone()),
              page_size: LIST_PAGE_SIZE,
              ...(pageParam ? { page_token: pageParam } : {}),
            },
          },
        }),
      ),
    initialPageParam: "",
    getNextPageParam: (last) => last.next_page_token || undefined,
    placeholderData: keepPreviousData,
    enabled,
  });

  const { hasNextPage, isFetchingNextPage, fetchNextPage } = query;
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) void fetchNextPage();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  return query;
}

/** `matched` for filters not applied yet (mobile filter sheet «Показать N»), one row per request. */
export function useDocumentCount(filters: DocumentFilters, { enabled }: { enabled: boolean }) {
  return useQuery({
    queryKey: queryKeys.documentCount(filters),
    queryFn: async () => {
      const list = await call(
        api.GET("/api/v1/documents", {
          params: { query: { ...toListQuery(filters, browserTimeZone()), page_size: 1 } },
        }),
      );
      return list.matched;
    },
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: queryKeys.document(id),
    queryFn: async () => {
      const { data, response } = await request(
        api.GET("/api/v1/documents/{document_id}", { params: { path: { document_id: id } } }),
      );
      return { document: data, etag: response.headers.get("ETag") ?? "" };
    },
    retry: (count, error) => !isApiError(error, "not_found") && count < 2,
  });
}

export type DocumentWithEtag = { document: DocumentFull; etag: string };

export async function patchDocument(
  id: string,
  etag: string,
  patch: DocumentPatch,
): Promise<DocumentWithEtag> {
  const { data, response } = await request(
    api.PATCH("/api/v1/documents/{document_id}", {
      params: { path: { document_id: id }, header: { "If-Match": etag, ...(await csrfHeader()) } },
      body: patch,
    }),
  );
  return { document: data, etag: response.headers.get("ETag") ?? "" };
}

/** Puts the saved card into the cache and marks lists stale (their `has_note`, order or dates changed). */
export function storeDocument(queryClient: QueryClient, saved: DocumentWithEtag): void {
  queryClient.setQueryData(queryKeys.document(saved.document.id), saved);
  void queryClient.invalidateQueries({ queryKey: queryKeys.allDocuments });
}

export function useUpdateDocument(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ etag, patch }: { etag: string; patch: DocumentPatch }) =>
      patchDocument(id, etag, patch),
    onSuccess: (saved) => storeDocument(queryClient, saved),
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, etag }: { id: string; etag: string }) =>
      call(
        api.DELETE("/api/v1/documents/{document_id}", {
          params: {
            path: { document_id: id },
            header: { "If-Match": etag, ...(await csrfHeader()) },
          },
        }),
      ),
    onSuccess: (_, { id }) => {
      queryClient.removeQueries({ queryKey: queryKeys.document(id) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.allDocuments });
      void queryClient.invalidateQueries({ queryKey: queryKeys.workspace });
    },
  });
}

/** Card of a list row for its ETag: list items carry `version`, and the ETag is `"v{version}"`. */
export async function fetchDocumentEtag(id: string): Promise<string> {
  const { response } = await request(
    api.GET("/api/v1/documents/{document_id}", { params: { path: { document_id: id } } }),
  );
  return response.headers.get("ETag") ?? "";
}

export function useCreateExport() {
  return useMutation({
    mutationFn: async ({ body, idempotencyKey }: { body: ExportCreate; idempotencyKey: string }) =>
      call(
        api.POST("/api/v1/exports", {
          params: { header: { "Idempotency-Key": idempotencyKey, ...(await csrfHeader()) } },
          body,
        }),
      ),
  });
}

/** Creates the archive with the consent given on onboarding (FE-11) and opens its session. */
export function useCreateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      idempotencyKey,
      policyVersion,
    }: {
      idempotencyKey: string;
      policyVersion: string;
    }) =>
      call(
        api.POST("/api/v1/workspaces", {
          params: { header: { "Idempotency-Key": idempotencyKey } },
          body: {
            consent: { policy_version: policyVersion, accepted: true },
            timezone: browserTimeZone(),
          },
        }),
      ),
    onSuccess: (created) => {
      setCsrfToken(created.csrf_token);
      queryClient.setQueryData<Session>(queryKeys.session, {
        workspace_id: created.workspace.id,
        csrf_token: created.csrf_token,
        scopes: created.scopes,
        timezone: browserTimeZone(),
      });
    },
  });
}

/** Opens an archive by its access key; everything cached for the previous archive is dropped. */
export function useOpenByKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (accessKey: string) =>
      call(api.POST("/api/v1/sessions", { body: { access_key: accessKey } })),
    onSuccess: (session) => {
      setCsrfToken(session.csrf_token);
      queryClient.clear();
      queryClient.setQueryData(queryKeys.session, session);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () =>
      call(api.DELETE("/api/v1/sessions/current", { params: { header: await csrfHeader() } })),
    onSuccess: () => forgetArchive(queryClient),
  });
}

export function useRotateKey() {
  return useMutation({
    mutationFn: async (idempotencyKey: string) =>
      call(
        api.POST("/api/v1/workspace/access-key", {
          params: { header: { "Idempotency-Key": idempotencyKey, ...(await csrfHeader()) } },
        }),
      ),
  });
}

/** Deletes the archive with the `If-Match` of its summary, loading the summary if it is not cached yet. */
export function useDeleteWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { etag } = await queryClient.ensureQueryData({
        queryKey: queryKeys.workspace,
        queryFn: fetchWorkspace,
      });
      return call(
        api.DELETE("/api/v1/workspace", {
          params: { header: { "If-Match": etag, ...(await csrfHeader()) } },
        }),
      );
    },
  });
}

/** After logout or archive deletion this browser has no session; cached archive data must go too. */
export function forgetArchive(queryClient: QueryClient): void {
  setCsrfToken(null);
  queryClient.clear();
  queryClient.setQueryData(queryKeys.session, null);
}

export { newIdempotencyKey };
