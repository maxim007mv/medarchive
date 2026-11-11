import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { useCountdown } from "./use-countdown";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

test("FE-21: counts the Retry-After seconds down and then stops ticking", () => {
  const { result } = renderHook(() => useCountdown(3, "error"));
  expect(result.current).toBe(3);

  act(() => vi.advanceTimersByTime(2000));
  expect(result.current).toBe(1);

  act(() => vi.advanceTimersByTime(1000));
  expect(result.current).toBeNull();
  expect(vi.getTimerCount()).toBe(0);
});

test("FE-21: unmounting in the middle of the wait clears the timer", () => {
  const { unmount } = renderHook(() => useCountdown(30, "error"));

  unmount();

  expect(vi.getTimerCount()).toBe(0);
});
