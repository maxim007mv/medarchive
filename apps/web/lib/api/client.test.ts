import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { api, call, csrfHeader, request, setCsrfToken } from "./client";
import { useIsOnline } from "./connectivity";
import { ApiError, isApiError, NetworkError, pointerToField, problemTitle } from "./errors";

const problem = (code: string, status: number, title = "Заголовок") => ({
  type: `urn:problem-type:medarchive:${code}`,
  title,
  status,
  code,
  request_id: "req_1",
});

function respond(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  const contentType = status >= 400 ? "application/problem+json" : "application/json";
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": contentType, ...headers },
  });
}

const fetchMock = vi.fn<(request: Request) => Promise<Response>>();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  setCsrfToken(null);
});

afterEach(() => {
  fetchMock.mockReset();
  vi.unstubAllGlobals();
});

describe("request", () => {
  test("returns data and the response for 2xx", async () => {
    fetchMock.mockResolvedValue(
      respond(200, { workspace_id: "w", csrf_token: "t", scopes: [] }, { ETag: '"w1"' }),
    );

    const { data, response } = await request(api.GET("/api/v1/session"));

    expect(data.csrf_token).toBe("t");
    expect(response.headers.get("ETag")).toBe('"w1"');
  });

  test("turns problem+json into ApiError with Retry-After", async () => {
    fetchMock.mockResolvedValue(
      respond(429, problem("rate_limited", 429), { "Retry-After": "41" }),
    );

    const error = await call(api.GET("/api/v1/session")).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "rate_limited", status: 429, retryAfterSec: 41 });
  });

  test("a bare 5xx from the proxy means the API is unreachable", async () => {
    fetchMock.mockResolvedValue(new Response("Internal Server Error", { status: 500 }));

    await expect(call(api.GET("/api/v1/session"))).rejects.toBeInstanceOf(NetworkError);
  });

  test("other thrown errors are not hidden as network errors", async () => {
    fetchMock.mockRejectedValue(new RangeError("bug"));

    await expect(call(api.GET("/api/v1/session"))).rejects.toBeInstanceOf(RangeError);
  });

  test("Retry-After that is not a number gives no countdown", async () => {
    fetchMock.mockResolvedValue(
      respond(429, problem("rate_limited", 429), { "Retry-After": "soon" }),
    );

    await expect(call(api.GET("/api/v1/session"))).rejects.toMatchObject({ retryAfterSec: null });
  });

  test("a failed fetch is a NetworkError", async () => {
    fetchMock.mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(call(api.GET("/api/v1/session"))).rejects.toBeInstanceOf(NetworkError);
  });
});

describe("csrfHeader", () => {
  test("loads the session once and reuses the token", async () => {
    fetchMock.mockResolvedValue(respond(200, { workspace_id: "w", csrf_token: "tok", scopes: [] }));

    expect(await csrfHeader()).toEqual({ "X-CSRF-Token": "tok" });
    expect(await csrfHeader()).toEqual({ "X-CSRF-Token": "tok" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  test("the token goes on mutating requests (TC-093)", async () => {
    setCsrfToken("tok");
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await call(api.DELETE("/api/v1/sessions/current", { params: { header: await csrfHeader() } }));

    expect(fetchMock.mock.calls[0]?.[0].headers.get("X-CSRF-Token")).toBe("tok");
  });
});

describe("connectivity (FE-21)", () => {
  test("a failed request turns the app offline and the next answer back online", async () => {
    const { result, rerender } = renderHook(() => useIsOnline());
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    await call(api.GET("/api/v1/session")).catch(() => undefined);
    rerender();
    expect(result.current).toBe(false);

    fetchMock.mockResolvedValueOnce(respond(401, problem("unauthenticated", 401)));
    await call(api.GET("/api/v1/session")).catch(() => undefined);
    rerender();
    expect(result.current).toBe(true);
  });
});

describe("problem helpers", () => {
  test("N in the title becomes the seconds left", () => {
    const rateLimited = problem(
      "rate_limited",
      429,
      "Слишком много действий подряд. Повторите через N с",
    );

    expect(problemTitle(rateLimited as never, 12)).toBe(
      "Слишком много действий подряд. Повторите через 12 с",
    );
  });

  test("without a countdown the title is shown as is", () => {
    const rateLimited = problem("rate_limited", 429, "Повторите через N с");

    expect(problemTitle(rateLimited as never, null)).toBe("Повторите через N с");
  });

  test("isApiError checks the code when asked", () => {
    const error = new ApiError(problem("not_found", 404) as never, null);

    expect(isApiError(error)).toBe(true);
    expect(isApiError(error, "not_found")).toBe(true);
    expect(isApiError(error, "version_conflict")).toBe(false);
    expect(isApiError(new Error("x"))).toBe(false);
  });

  test("pointer names the form field", () => {
    expect(pointerToField("/document_date")).toBe("document_date");
    expect(pointerToField("/consent/accepted")).toBe("consent");
  });
});
