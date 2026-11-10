import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WifiOff } from "lucide-react";
import { afterEach, expect, test, vi } from "vitest";

import { t, texts } from "@/lib/texts";

import { seriousViolations } from "./axe";
import { Banner } from "./banner";
import { Button } from "./button";
import { Skeleton, useDelayedFlag } from "./skeleton";
import { ToastProvider, useToast, type ToastOptions } from "./toast";

afterEach(() => {
  vi.useRealTimers();
});

function ToastTrigger(toast: ToastOptions) {
  const show = useToast();
  return <Button onClick={() => show(toast)}>{texts["upload.save"]}</Button>;
}

const added = t("upload.toast.added", { title: "ЭКГ покоя" });

test("FE-07: a toast is announced through a polite live region", async () => {
  render(
    <ToastProvider>
      <ToastTrigger title={added} />
    </ToastProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: texts["upload.save"] }));

  const announcement = await screen.findByText(added, { selector: '[aria-live="polite"]' });
  expect(announcement).toHaveAttribute("role", "status");
  expect(document.querySelector('[aria-live="assertive"]')).toBeNull();
});

test("FE-07: the toast action runs its handler", async () => {
  const onOpen = vi.fn();
  render(
    <ToastProvider>
      <ToastTrigger title={added} action={{ label: texts["upload.toast.open"], onClick: onOpen }} />
    </ToastProvider>,
  );

  await userEvent.click(screen.getByRole("button", { name: texts["upload.save"] }));
  await userEvent.click(await screen.findByRole("button", { name: texts["upload.toast.open"] }));

  expect(onOpen).toHaveBeenCalledOnce();
});

test("FE-07: a toast disappears after 4 s by default", async () => {
  vi.useFakeTimers();
  render(
    <ToastProvider>
      <ToastTrigger title={texts["delete.toast"]} />
    </ToastProvider>,
  );
  const shownToast = () => screen.queryByText(texts["delete.toast"], { selector: "li *" });

  fireEvent.click(screen.getByRole("button", { name: texts["upload.save"] }));
  await act(() => vi.advanceTimersByTimeAsync(3900));
  expect(shownToast()).toBeInTheDocument();
  await act(() => vi.advanceTimersByTimeAsync(200));

  expect(shownToast()).not.toBeInTheDocument();
});

test("FE-07: useToast outside the provider fails loudly", () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  expect(() => renderHook(() => useToast())).toThrow("ToastProvider");
});

test("FE-07: useDelayedFlag turns on only after the delay and resets at once", async () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(({ active }) => useDelayedFlag(active, 1000), {
    initialProps: { active: true },
  });

  await act(() => vi.advanceTimersByTimeAsync(999));
  expect(result.current).toBe(false);
  await act(() => vi.advanceTimersByTimeAsync(1));
  expect(result.current).toBe(true);

  rerender({ active: false });
  expect(result.current).toBe(false);
  rerender({ active: true });
  expect(result.current).toBe(false);
  await act(() => vi.advanceTimersByTimeAsync(1000));
  expect(result.current).toBe(true);
});

test("FE-07: a request shorter than the delay never shows the skeleton", async () => {
  vi.useFakeTimers();
  const { result, rerender } = renderHook(({ active }) => useDelayedFlag(active), {
    initialProps: { active: true },
  });

  await act(() => vi.advanceTimersByTimeAsync(600));
  rerender({ active: false });
  await act(() => vi.advanceTimersByTimeAsync(1000));

  expect(result.current).toBe(false);
});

test("FE-07: banner and skeleton have no serious axe violations", async () => {
  const { container } = render(
    <div>
      <Banner
        icon={WifiOff}
        title={texts["offline.banner.title"]}
        action={
          <Button variant="secondary" size="sm">
            {texts["offline.banner.retry"]}
          </Button>
        }
      >
        {texts["offline.banner.text"]}
      </Banner>
      <div role="status" aria-label={texts["list.skeleton"]}>
        <Skeleton className="h-3 w-40" />
      </div>
    </div>,
  );

  expect(screen.getByRole("status", { name: texts["list.skeleton"] })).toBeInTheDocument();
  expect(await seriousViolations(container)).toEqual([]);
});
