import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import type { ReactNode } from "react";
import { vi } from "vitest";

import { setCsrfToken } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Handler = (request: Request) => Response | Promise<Response>;

/**
 * In-memory stand-in for the API in component tests: `"PATCH /api/v1/documents/d1"` → handler.
 * Unknown routes fail the test loudly instead of hanging.
 */
export function mockApi(routes: Record<string, Handler>) {
  const calls: Request[] = [];
  const fetchMock = vi.fn(async (input: Request) => {
    const url = new URL(input.url);
    const route = `${input.method} ${url.pathname}`;
    calls.push(input.clone());
    const handler = routes[route];
    if (!handler) throw new Error(`unexpected request ${route}`);
    return handler(input);
  });
  vi.stubGlobal("fetch", fetchMock);
  setCsrfToken("csrf-test");
  return { calls, routes };
}

export function json(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": status >= 400 ? "application/problem+json" : "application/json",
      ...headers,
    },
  });
}

export function problem(status: number, code: string, title: string, extra: object = {}): Response {
  return json(status, {
    type: `urn:problem-type:medarchive:${code}`,
    title,
    status,
    code,
    request_id: "req_test",
    ...extra,
  });
}

export function makeDocument(
  patch: Partial<components["schemas"]["Document"]> = {},
): components["schemas"]["Document"] {
  return {
    id: "d1",
    title: "Общий анализ крови",
    type: "analysis",
    document_date: "2026-04-08",
    uploaded_at: "2026-11-10T16:02:11Z",
    updated_at: "2026-11-10T16:02:11Z",
    note: null,
    file: { original_name: "01-general-blood-test.pdf", size_bytes: 79114, page_count: 1 },
    version: 1,
    ...patch,
  };
}

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

export function Wrapper({
  client,
  searchParams = "",
  children,
}: {
  client: QueryClient;
  searchParams?: string;
  children: ReactNode;
}) {
  return (
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter searchParams={searchParams}>{children}</NuqsTestingAdapter>
    </QueryClientProvider>
  );
}
