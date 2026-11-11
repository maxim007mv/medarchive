import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import type { ReactNode } from "react";
import { vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import { setCsrfToken } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

// jsdom has no ResizeObserver; Radix radio and checkbox measure themselves with it.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// …and no matchMedia, which the theme switch in the header reads.
window.matchMedia ??= (query: string) =>
  ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  }) satisfies MediaQueryList;

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

/** Stand-in for the storage XHR of presigned POST: the test drives progress and the outcome. */
export class FakeXhr {
  static instances: FakeXhr[] = [];
  upload: { onprogress?: (event: ProgressEvent) => void } = {};
  status = 0;
  url = "";
  body?: FormData;
  onload?: () => void;
  onerror?: () => void;
  onabort?: () => void;
  constructor() {
    FakeXhr.instances.push(this);
  }
  open(_method: string, url: string) {
    this.url = url;
  }
  send(body: FormData) {
    this.body = body;
  }
  abort() {
    this.onabort?.();
  }
  progress(percent: number) {
    this.upload.onprogress?.({
      lengthComputable: true,
      loaded: percent,
      total: 100,
    } as ProgressEvent);
  }
  succeed() {
    this.progress(100);
    this.status = 204;
    this.onload?.();
  }
  static install() {
    FakeXhr.instances = [];
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
  }
  static get last(): FakeXhr {
    const xhr = FakeXhr.instances.at(-1);
    if (!xhr) throw new Error("no storage upload was started");
    return xhr;
  }
}

export function pdfFile(name = "01-general-blood-test.pdf", size = 79_114): File {
  const content = new Uint8Array(size);
  content.set(new TextEncoder().encode("%PDF-1.4"));
  return new File([content], name, { type: "application/pdf" });
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
      <NuqsTestingAdapter searchParams={searchParams}>
        <ToastProvider>{children}</ToastProvider>
      </NuqsTestingAdapter>
    </QueryClientProvider>
  );
}
