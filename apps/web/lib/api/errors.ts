import type { components } from "./schema";

export type Problem = components["schemas"]["Problem"];
export type ProblemCode = Problem["code"];

/** RFC 9457 problem from the API. `title` is shown to the person as is (06-api-contract, section 8). */
export class ApiError extends Error {
  constructor(
    readonly problem: Problem,
    readonly retryAfterSec: number | null,
  ) {
    super(`api error ${problem.status} ${problem.code}`);
    this.name = "ApiError";
  }

  get code(): ProblemCode {
    return this.problem.code;
  }

  get status(): number {
    return this.problem.status;
  }
}

/** The server could not be reached: offline, proxy without upstream, aborted transfer. */
export class NetworkError extends Error {
  constructor() {
    super("network error");
    this.name = "NetworkError";
  }
}

function isProblem(body: unknown): body is Problem {
  if (typeof body !== "object" || body === null) return false;
  const { code, title, status } = body as Record<string, unknown>;
  return typeof code === "string" && typeof title === "string" && typeof status === "number";
}

function parseRetryAfter(response: Response): number | null {
  const seconds = Number(response.headers.get("Retry-After"));
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : null;
}

/**
 * Error for a non-2xx response. A body that is not a problem means the API itself did not answer
 * (the Next proxy returns a bare 5xx when the upstream is down), so it counts as no connection.
 */
export function errorFromResponse(response: Response, body: unknown): ApiError | NetworkError {
  if (isProblem(body)) return new ApiError(body, parseRetryAfter(response));
  return new NetworkError();
}

export function isApiError(error: unknown, code?: ProblemCode): error is ApiError {
  return error instanceof ApiError && (code === undefined || error.code === code);
}

/** `rate_limited` and `ai_busy` titles carry `N` in place of the seconds from `Retry-After`. */
export function problemTitle(problem: Problem, secondsLeft: number | null): string {
  return secondsLeft === null ? problem.title : problem.title.replace(/\bN\b/, String(secondsLeft));
}

/** Field name for a JSON pointer of `errors[]`: `/document_date` → `document_date`. */
export function pointerToField(pointer: string): string {
  return pointer.replace(/^\//, "").split("/")[0] ?? "";
}
