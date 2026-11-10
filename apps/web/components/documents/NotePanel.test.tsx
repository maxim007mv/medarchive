import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { type DocumentWithEtag, queryKeys } from "@/lib/api/queries";

import { NOTE_UNDO_MS, NotePanel } from "./NotePanel";
import { json, makeDocument, makeQueryClient, mockApi, problem, Wrapper } from "./test-utils";
import { NOTE_SAVE_DELAY_MS } from "./use-note-autosave";

const PATCH = "PATCH /api/v1/documents/d1";

function setup(note: string | null) {
  const client = makeQueryClient();
  client.setQueryData<DocumentWithEtag>(queryKeys.document("d1"), {
    document: makeDocument({ note }),
    etag: '"v1"',
  });
  render(
    <Wrapper client={client}>
      <NotePanel documentId="d1" />
    </Wrapper>,
  );
  return { client, user: userEvent.setup({ advanceTimers: vi.advanceTimersByTime }) };
}

const savedWith = (version: number) => async (request: Request) =>
  json(200, makeDocument({ note: (await request.json()).note, version }), {
    ETag: `"v${version}"`,
  });

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  sessionStorage.clear();
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("NotePanel (FE-18)", () => {
  test("TC-051: «Сохраняем…» then «Сохранено», with the counter", async () => {
    let release!: () => void;
    mockApi({
      [PATCH]: async (request) => {
        await new Promise<void>((resolve) => (release = resolve));
        return savedWith(2)(request);
      },
    });
    const { user } = setup(null);

    await user.type(screen.getByRole("textbox", { name: "Заметка" }), "Пересдать");
    expect(screen.getByText("9 / 2000 · сохраняется автоматически")).toBeInTheDocument();
    await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS));
    expect(screen.getByRole("status")).toHaveTextContent("Сохраняем…");

    await act(async () => release());

    expect(screen.getByRole("status")).toHaveTextContent("Сохранено");
  });

  test("a failed save shows «Не сохранилось. Повторить» and keeps the text", async () => {
    const responses = [problem(500, "internal", "x")];
    mockApi({ [PATCH]: (request) => responses.shift() ?? savedWith(2)(request) });
    const { user } = setup(null);
    const field = screen.getByRole("textbox", { name: "Заметка" });

    await user.type(field, "Текст");
    await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Не сохранилось. Повторить"),
    );
    expect(field).toHaveValue("Текст");
    await user.click(screen.getByRole("button", { name: "Повторить" }));
    expect(await screen.findByText("Сохранено")).toBeInTheDocument();
  });

  test("«Очистить» sends null at once and «Вернуть» in the 6 s toast restores the note", async () => {
    const bodies: unknown[] = [];
    let version = 1;
    mockApi({
      [PATCH]: async (request) => {
        bodies.push(await request.clone().json());
        version += 1;
        return savedWith(version)(request);
      },
    });
    const { user } = setup("Холестерин выше нормы");

    await user.click(screen.getByRole("button", { name: "Очистить" }));

    expect(screen.getByRole("textbox", { name: "Заметка" })).toHaveValue("");
    expect(await screen.findByText("Заметка очищена")).toBeInTheDocument();
    expect(NOTE_UNDO_MS).toBe(6000);
    await user.click(screen.getByRole("button", { name: "Вернуть" }));

    expect(screen.getByRole("textbox", { name: "Заметка" })).toHaveValue("Холестерин выше нормы");
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(bodies).toEqual([{ note: null }, { note: "Холестерин выше нормы" }]);
  });

  test("TC-053: 2001 characters turn the counter into an error and block saving", async () => {
    const api = mockApi({});
    setup(null);
    const field = screen.getByRole("textbox", { name: "Заметка" });

    act(() => {
      field.focus();
    });
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).paste("а".repeat(2001));
    await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS));

    expect(screen.getByText("Заметка длиннее 2000 символов")).toBeInTheDocument();
    expect(screen.getByText("Сократите заметку до 2000 символов")).toBeInTheDocument();
    expect(field).toHaveAttribute("aria-invalid", "true");
    expect(api.calls).toHaveLength(0);
  });

  test("TC-052: a conflict keeps the text and offers «Обновить»", async () => {
    mockApi({
      [PATCH]: () =>
        problem(
          412,
          "version_conflict",
          "Документ изменился в другой вкладке. Обновите, чтобы увидеть новую версию",
        ),
    });
    const { user } = setup("Старая");

    await user.type(screen.getByRole("textbox", { name: "Заметка" }), " правка");
    await act(() => vi.advanceTimersByTimeAsync(NOTE_SAVE_DELAY_MS));

    expect(
      screen.getByText("Документ изменился в другой вкладке. Обновите, чтобы увидеть новую версию"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Обновить" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Заметка" })).toHaveValue("Старая правка");
  });
});
