import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { type DocumentWithEtag, queryKeys } from "@/lib/api/queries";

import { json, makeDocument, makeQueryClient, mockApi, problem, Wrapper } from "./test-utils";
import { NOTE_SAVE_DELAY_MS, useNoteAutosave } from "./use-note-autosave";

const PATCH = "PATCH /api/v1/documents/d1";

function setup(note: string | null = null) {
  const client = makeQueryClient();
  client.setQueryData<DocumentWithEtag>(queryKeys.document("d1"), {
    document: makeDocument({ note }),
    etag: '"v1"',
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <Wrapper client={client}>{children}</Wrapper>
  );
  const hook = renderHook(() => useNoteAutosave("d1"), { wrapper });
  const cachedNote = () =>
    client.getQueryData<DocumentWithEtag>(queryKeys.document("d1"))?.document.note;
  return { ...hook, client, cachedNote };
}

async function typeAndWait(result: { current: ReturnType<typeof useNoteAutosave> }, text: string) {
  act(() => result.current.setDraft(text));
  await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS));
}

beforeEach(() => {
  vi.useFakeTimers();
  sessionStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("note autosave (FE-18)", () => {
  test("saves 800 ms after the last keystroke with If-Match, then clears the copy (TC-051)", async () => {
    const api = mockApi({
      [PATCH]: async (request) =>
        json(200, makeDocument({ note: (await request.json()).note, version: 2 }), {
          ETag: '"v2"',
        }),
    });
    const { result, client } = setup();

    act(() => result.current.setDraft("Пересдать"));
    await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS - 1));
    expect(api.calls).toHaveLength(0);
    expect(sessionStorage.getItem("medarchive:note:d1")).toBe("Пересдать");

    await act(() => vi.advanceTimersByTimeAsync(1));

    expect(api.calls).toHaveLength(1);
    expect(api.calls[0]?.headers.get("If-Match")).toBe('"v1"');
    expect(await api.calls[0]?.json()).toEqual({ note: "Пересдать" });
    expect(result.current.status).toBe("saved");
    expect(sessionStorage.getItem("medarchive:note:d1")).toBeNull();
    expect(client.getQueryData<DocumentWithEtag>(queryKeys.document("d1"))?.etag).toBe('"v2"');
  });

  test("shows the note in the cache at once and rolls it back when saving fails", async () => {
    let fail!: () => void;
    mockApi({
      [PATCH]: () =>
        new Promise<Response>((resolve) => (fail = () => resolve(problem(500, "internal", "x")))),
    });
    const { result, cachedNote } = setup("Старая");

    await typeAndWait(result, "Новая");
    expect(result.current.status).toBe("saving");
    expect(cachedNote()).toBe("Новая");

    await act(async () => fail());

    expect(cachedNote()).toBe("Старая");
    expect(result.current.status).toBe("failed");
    expect(result.current.draft).toBe("Новая");
    expect(sessionStorage.getItem("medarchive:note:d1")).toBe("Новая");
  });

  test("retry after a failure sends the text again", async () => {
    const responses = [
      problem(500, "internal", "x"),
      json(200, makeDocument({ note: "Текст" }), { ETag: '"v2"' }),
    ];
    const api = mockApi({ [PATCH]: () => responses.shift()! });
    const { result } = setup();

    await typeAndWait(result, "Текст");
    expect(result.current.status).toBe("failed");

    await act(async () => result.current.retry());

    expect(api.calls).toHaveLength(2);
    expect(result.current.status).toBe("saved");
  });

  test("412 is a conflict and the typed text stays (TC-052)", async () => {
    mockApi({
      [PATCH]: () => problem(412, "version_conflict", "Документ изменился в другой вкладке"),
    });
    const { result } = setup("Старая");

    await typeAndWait(result, "Моя правка");

    expect(result.current.status).toBe("conflict");
    expect(result.current.draft).toBe("Моя правка");
  });

  test("over 2000 characters nothing is sent (TC-053)", async () => {
    const api = mockApi({});
    const { result } = setup();

    await typeAndWait(result, "а".repeat(2001));

    expect(result.current.status).toBe("tooLong");
    expect(api.calls).toHaveLength(0);
  });

  test("text typed during a save goes next, with the new ETag", async () => {
    const etags: string[] = [];
    let release!: () => void;
    const api = mockApi({
      [PATCH]: async (request) => {
        etags.push(request.headers.get("If-Match") ?? "");
        const body = await request.json();
        if (etags.length === 1) await new Promise<void>((resolve) => (release = resolve));
        return json(200, makeDocument({ note: body.note, version: etags.length + 1 }), {
          ETag: `"v${etags.length + 1}"`,
        });
      },
    });
    const { result } = setup();

    await typeAndWait(result, "Пер");
    await typeAndWait(result, "Пересдать");
    expect(api.calls).toHaveLength(1);

    await act(async () => release());

    expect(etags).toEqual(['"v1"', '"v2"']);
    expect(await api.calls[1]?.json()).toEqual({ note: "Пересдать" });
    expect(result.current.status).toBe("saved");
  });

  test("an empty note is sent as null", async () => {
    const api = mockApi({
      [PATCH]: () => json(200, makeDocument({ note: null }), { ETag: '"v2"' }),
    });
    const { result } = setup("Было");

    await act(async () => result.current.replace(""));

    expect(await api.calls[0]?.json()).toEqual({ note: null });
  });

  test("hiding the page sends the unsaved note with keepalive", async () => {
    const api = mockApi({
      [PATCH]: () => json(200, makeDocument({ note: "Черновик" }), { ETag: '"v2"' }),
    });
    const { result } = setup();
    act(() => result.current.setDraft("Черновик"));

    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    await act(async () => document.dispatchEvent(new Event("visibilitychange")));

    expect(api.calls).toHaveLength(1);
    expect(api.calls[0]?.keepalive).toBe(true);
    await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS));
    expect(api.calls).toHaveLength(1);
  });

  test("unmounting drops the pending 800 ms timer and the page listeners; the copy stays", async () => {
    const api = mockApi({});
    const { result, unmount } = setup();
    act(() => result.current.setDraft("Черновик"));

    unmount();
    await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS));
    vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    document.dispatchEvent(new Event("visibilitychange"));
    window.dispatchEvent(new Event("beforeunload"));

    expect(api.calls).toHaveLength(0);
    expect(sessionStorage.getItem("medarchive:note:d1")).toBe("Черновик");
  });

  test("a copy left in sessionStorage is restored and saved", async () => {
    sessionStorage.setItem("medarchive:note:d1", "Не дошло");
    const api = mockApi({
      [PATCH]: () => json(200, makeDocument({ note: "Не дошло" }), { ETag: '"v2"' }),
    });
    const { result } = setup();
    expect(result.current.draft).toBe("Не дошло");

    await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS));

    expect(api.calls).toHaveLength(1);
    expect(result.current.status).toBe("saved");
  });
});
