import createClient from "openapi-fetch";

import { reportRequestOutcome } from "./connectivity";
import { errorFromResponse, NetworkError } from "./errors";
import type { paths } from "./schema";

/**
 * Typed client for `/api/v1/*` (FE-10). The browser talks to its own origin; Next proxies to the API,
 * so the `__Host-ma_sid` cookie goes along without CORS (ADR-048).
 */
export const api = createClient<paths>({
  baseUrl: typeof window === "undefined" ? "" : window.location.origin,
  // Resolved per call: openapi-fetch would otherwise capture the fetch present at import time.
  fetch: (request) => globalThis.fetch(request),
  querySerializer: { array: { style: "form", explode: false } },
});

api.use({
  onResponse({ response }) {
    reportRequestOutcome({ reachable: response.status < 500 || isProblemResponse(response) });
  },
  onError() {
    reportRequestOutcome({ reachable: false });
  },
});

function isProblemResponse(response: Response): boolean {
  return response.headers.get("Content-Type")?.startsWith("application/problem+json") ?? false;
}

let csrfToken: string | null = null;

/** Token from `GET /api/v1/session` or from a response that created the session. */
export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

/** `X-CSRF-Token` for a mutating request; loads the session once if the token is not known yet. */
export async function csrfHeader(): Promise<{ "X-CSRF-Token": string }> {
  if (csrfToken === null) {
    const { data } = await request(api.GET("/api/v1/session"));
    csrfToken = data.csrf_token;
  }
  return { "X-CSRF-Token": csrfToken };
}

/** Same header without waiting, for `keepalive` requests sent while the page is being hidden. */
export function csrfHeaderSync(): { "X-CSRF-Token": string } | null {
  return csrfToken === null ? null : { "X-CSRF-Token": csrfToken };
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Awaits an openapi-fetch call and turns problem+json and transport failures into thrown errors. */
export async function request<T>(
  call: Promise<Result<T>>,
): Promise<{ data: T; response: Response }> {
  let result: Result<T>;
  try {
    result = await call;
  } catch (error) {
    if (error instanceof TypeError) throw new NetworkError();
    throw error;
  }
  if (!result.response.ok) throw errorFromResponse(result.response, result.error);
  return { data: result.data as T, response: result.response };
}

export async function call<T>(promise: Promise<Result<T>>): Promise<T> {
  return (await request(promise)).data;
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
