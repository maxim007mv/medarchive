import { ApiError, problemTitle } from "@/lib/api/errors";
import { errorTitles } from "@/lib/texts";

import { useCountdown } from "./use-countdown";

export type ProblemView = {
  /** `title` of the problem as is, `N` replaced by the seconds left (FE-21). */
  title: string;
  /** For «Подробнее» under server errors: the support can find the request in the logs. */
  requestId: string | null;
  /** Seconds the action stays blocked after 429. */
  waitSeconds: number | null;
};

/** What to show for a failed request; `null` once a 429 wait is over or when there is no error. */
export function useProblem(error: unknown): ProblemView | null {
  const apiError = error instanceof ApiError ? error : null;
  const waitSeconds = useCountdown(apiError?.retryAfterSec ?? null, error);

  if (!error) return null;
  if (!apiError) return { title: errorTitles.internal, requestId: null, waitSeconds: null };
  if (apiError.retryAfterSec !== null && apiError.status === 429 && waitSeconds === null)
    return null;
  return {
    title: problemTitle(apiError.problem, waitSeconds),
    requestId: apiError.status >= 500 ? apiError.problem.request_id : null,
    waitSeconds,
  };
}
