import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { DEFAULT_FILTERS } from "@/lib/filters";

import { csrfHeader, setCsrfToken } from "./client";
import {
  fetchDocumentEtag,
  queryKeys,
  useCreateExport,
  useCreateWorkspace,
  useDeleteDocument,
  useDeleteWorkspace,
  useDocument,
  useDocumentCount,
  useDocuments,
  useLogout,
  useOpenByKey,
  useRotateKey,
  useSession,
  useUpdateDocument,
  useWorkspace,
} from "./queries";

type Route = (request: Request) => Response;
const calls: Request[] = [];
let routes: Record<string, Route> = {};

const json = (status: number, body: unknown, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": status >= 400 ? "application/problem+json" : "application/json",
      ...headers,
    },
  });
const problem = (status: number, code: string) =>
  json(status, {
    type: `urn:problem-type:medarchive:${code}`,
    title: code,
    status,
    code,
    request_id: "r",
  });
const list = (items: { id: string }[], next = "", matched = items.length) => ({
  items: items.map((item) => ({
    ...item,
    title: item.id,
    type: "other",
    document_date: null,
    uploaded_at: "2026-11-10T09:00:00Z",
    has_note: false,
    size_bytes: 1,
    version: 1,
  })),
  total: 6,
  matched,
  undated_excluded: 0,
  next_page_token: next,
});
const document = (id: string) => ({
  id,
  title: id,
  type: "other",
  document_date: null,
  uploaded_at: "2026-11-10T09:00:00Z",
  updated_at: "2026-11-10T09:00:00Z",
  note: null,
  file: { original_name: "a.pdf", size_bytes: 1, page_count: 1 },
  version: 2,
});

let client: QueryClient;
const wrapper = ({ children }: { children: ReactNode }) =>
  createElement(QueryClientProvider, { client }, children);

beforeEach(() => {
  calls.length = 0;
  routes = {};
  client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  setCsrfToken("tok");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      calls.push(request.clone());
      const route = routes[`${request.method} ${new URL(request.url).pathname}`];
      if (!route) throw new Error(`unexpected ${request.method} ${request.url}`);
      return route(request);
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("session", () => {
  test("a session sets the CSRF token", async () => {
    routes["GET /api/v1/session"] = () =>
      json(200, { workspace_id: "w", csrf_token: "fresh", scopes: [] });
    setCsrfToken(null);

    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.data?.csrf_token).toBe("fresh"));
    expect(await csrfHeader()).toEqual({ "X-CSRF-Token": "fresh" });
  });

  test("401 means no archive in this browser", async () => {
    routes["GET /api/v1/session"] = () => problem(401, "unauthenticated");

    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
  });

  test("other errors stay errors", async () => {
    routes["GET /api/v1/session"] = () => problem(500, "internal");

    const { result } = renderHook(() => useSession(), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe("list", () => {
  test("loads every page with the filter query and page_size 200", async () => {
    const pages = [list([{ id: "a" }], "t2"), list([{ id: "b" }])];
    routes["GET /api/v1/documents"] = () => json(200, pages.shift());

    const { result } = renderHook(
      () => useDocuments({ ...DEFAULT_FILTERS, q: "анализ" }, { enabled: true }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));
    const [first, second] = calls.map((call) => new URL(call.url).searchParams);
    expect(first?.get("q")).toBe("анализ");
    expect(first?.get("page_size")).toBe("200");
    expect(second?.get("page_token")).toBe("t2");
  });

  test("the sheet counter asks one row and returns matched", async () => {
    routes["GET /api/v1/documents"] = () => json(200, list([{ id: "a" }], "", 3));

    const { result } = renderHook(
      () => useDocumentCount({ ...DEFAULT_FILTERS, type: ["conclusion"] }, { enabled: true }),
      { wrapper },
    );

    await waitFor(() => expect(result.current.data).toBe(3));
    const query = new URL(calls[0]!.url).searchParams;
    expect(query.get("page_size")).toBe("1");
    expect(query.get("type")).toBe("conclusion");
  });

  test("workspace comes with its ETag", async () => {
    routes["GET /api/v1/workspace"] = () =>
      json(200, { id: "w", created_at: "x", document_count: 6 }, { ETag: '"w3"' });

    const { result } = renderHook(() => useWorkspace({ enabled: true }), { wrapper });

    await waitFor(() => expect(result.current.data?.etag).toBe('"w3"'));
  });
});

describe("document", () => {
  test("the card keeps its ETag; PATCH sends If-Match and stores the new version", async () => {
    routes["GET /api/v1/documents/d1"] = () => json(200, document("d1"), { ETag: '"v2"' });
    routes["PATCH /api/v1/documents/d1"] = () =>
      json(200, { ...document("d1"), note: "x", version: 3 }, { ETag: '"v3"' });
    const invalidate = vi.spyOn(client, "invalidateQueries");

    const card = renderHook(() => useDocument("d1"), { wrapper });
    await waitFor(() => expect(card.result.current.data?.etag).toBe('"v2"'));
    const update = renderHook(() => useUpdateDocument("d1"), { wrapper });
    await act(() => update.result.current.mutateAsync({ etag: '"v2"', patch: { note: "x" } }));

    expect(calls.at(-1)?.headers.get("If-Match")).toBe('"v2"');
    expect(calls.at(-1)?.headers.get("X-CSRF-Token")).toBe("tok");
    expect(client.getQueryData<{ etag: string }>(queryKeys.document("d1"))?.etag).toBe('"v3"');
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["documents"] });
  });

  test("not_found is not retried", async () => {
    let count = 0;
    routes["GET /api/v1/documents/gone"] = () => {
      count += 1;
      return problem(404, "not_found");
    };
    client = new QueryClient();

    const { result } = renderHook(() => useDocument("gone"), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(count).toBe(1);
  });

  test("delete sends If-Match and drops the card from the cache", async () => {
    routes["DELETE /api/v1/documents/d1"] = () => new Response(null, { status: 204 });
    client.setQueryData(queryKeys.document("d1"), { document: document("d1"), etag: '"v2"' });

    const { result } = renderHook(() => useDeleteDocument(), { wrapper });
    await act(() => result.current.mutateAsync({ id: "d1", etag: '"v2"' }));

    expect(calls[0]?.headers.get("If-Match")).toBe('"v2"');
    expect(client.getQueryData(queryKeys.document("d1"))).toBeUndefined();
  });

  test("a response without ETag gives an empty one, so If-Match fails loudly on the server", async () => {
    routes["GET /api/v1/documents/d2"] = () => json(200, document("d2"));
    routes["GET /api/v1/workspace"] = () =>
      json(200, { id: "w", created_at: "x", document_count: 0 });

    expect(await fetchDocumentEtag("d2")).toBe("");
    const card = renderHook(() => useDocument("d2"), { wrapper });
    const workspace = renderHook(() => useWorkspace({ enabled: true }), { wrapper });
    await waitFor(() => expect(card.result.current.data?.etag).toBe(""));
    await waitFor(() => expect(workspace.result.current.data?.etag).toBe(""));
  });

  test("a list row gets its ETag from the card", async () => {
    routes["GET /api/v1/documents/d1"] = () => json(200, document("d1"), { ETag: '"v7"' });

    expect(await fetchDocumentEtag("d1")).toBe('"v7"');
  });
});

describe("archive and key", () => {
  test("creating the archive sends the consent and opens the session", async () => {
    routes["POST /api/v1/workspaces"] = () =>
      json(201, {
        workspace: { id: "w1", created_at: "x", document_count: 0 },
        access_key: "K",
        csrf_token: "new",
        scopes: [],
      });

    const { result } = renderHook(() => useCreateWorkspace(), { wrapper });
    await act(() =>
      result.current.mutateAsync({
        idempotencyKey: "key-1234567890abcdef",
        policyVersion: "2026-11-10",
      }),
    );

    expect(calls[0]?.headers.get("Idempotency-Key")).toBe("key-1234567890abcdef");
    expect(await calls[0]?.json()).toMatchObject({
      consent: { policy_version: "2026-11-10", accepted: true },
    });
    expect(client.getQueryData<{ workspace_id: string }>(queryKeys.session)?.workspace_id).toBe(
      "w1",
    );
    expect(await csrfHeader()).toEqual({ "X-CSRF-Token": "new" });
  });

  test("opening by key replaces everything cached for the previous archive", async () => {
    routes["POST /api/v1/sessions"] = () =>
      json(201, { workspace_id: "w2", csrf_token: "k", scopes: [] });
    client.setQueryData(queryKeys.document("old"), { document: document("old"), etag: "" });

    const { result } = renderHook(() => useOpenByKey(), { wrapper });
    await act(() => result.current.mutateAsync("7K3M-Q9TB-2XRA-HC4D-P8WN-6YFE"));

    expect(client.getQueryData(queryKeys.document("old"))).toBeUndefined();
    expect(client.getQueryData<{ workspace_id: string }>(queryKeys.session)?.workspace_id).toBe(
      "w2",
    );
  });

  test("logout forgets the archive", async () => {
    routes["DELETE /api/v1/sessions/current"] = () => new Response(null, { status: 204 });

    const { result } = renderHook(() => useLogout(), { wrapper });
    await act(() => result.current.mutateAsync());

    expect(client.getQueryData(queryKeys.session)).toBeNull();
  });

  test("a new key and the archive deletion carry their headers", async () => {
    routes["POST /api/v1/workspace/access-key"] = () =>
      json(201, { access_key: "N", revoked_previous: true });
    routes["DELETE /api/v1/workspace"] = () =>
      json(202, { status: "scheduled", purge_before: "2026-11-11T16:30:00Z" });

    const rotate = renderHook(() => useRotateKey(), { wrapper });
    await act(() => rotate.result.current.mutateAsync("rotate-key-0123456789"));
    const remove = renderHook(() => useDeleteWorkspace(), { wrapper });
    await act(() => remove.result.current.mutateAsync('"w3"'));

    expect(calls[0]?.headers.get("Idempotency-Key")).toBe("rotate-key-0123456789");
    expect(calls[1]?.headers.get("If-Match")).toBe('"w3"');
  });

  test("export sends its Idempotency-Key", async () => {
    routes["POST /api/v1/exports"] = () =>
      json(201, {
        id: "e",
        scope: "all",
        document_count: 6,
        total_bytes: 466000,
        content_url: "/x",
        expires_at: "x",
      });

    const { result } = renderHook(() => useCreateExport(), { wrapper });
    const created = await act(() =>
      result.current.mutateAsync({
        body: { scope: "all" },
        idempotencyKey: "export-key-0123456789",
      }),
    );

    expect(created.total_bytes).toBe(466000);
    expect(calls[0]?.headers.get("Idempotency-Key")).toBe("export-key-0123456789");
  });
});
