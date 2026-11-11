import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { MAX_UPLOAD_BYTES } from "@/lib/api/upload";

import {
  FakeXhr,
  json,
  makeDocument,
  makeQueryClient,
  mockApi,
  pdfFile,
  Wrapper,
} from "./test-utils";
import { UploadDialog } from "./UploadDialog";

const upload = (id: string) => ({
  upload_id: id,
  url: "http://localhost:9000/ma-quarantine",
  fields: { key: `q/${id}.bin`, policy: "p" },
  max_bytes: MAX_UPLOAD_BYTES,
  expires_at: "2026-11-10T16:15:10Z",
});

function setup(files: File[]) {
  const onSaved = vi.fn();
  const onClose = vi.fn();
  render(
    <Wrapper client={makeQueryClient()}>
      <UploadDialog initialFiles={files} onSaved={onSaved} onClose={onClose} />
    </Wrapper>,
  );
  return { onSaved, onClose, user: userEvent.setup() };
}

const saveButton = () => screen.getByRole("button", { name: /Сохранить в архив|Сохраняем…/ });

async function fillValidFields(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("radio", { name: "Анализ" }));
  await user.type(screen.getByLabelText("Дата документа"), "08042026");
}

beforeEach(() => {
  FakeXhr.install();
  vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-10T12:00:00+03:00") });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("UploadDialog (FE-12)", () => {
  test("TC-010: uploads with original_name, then saves the fields with an Idempotency-Key", async () => {
    const api = mockApi({
      "POST /api/v1/uploads": () => json(201, upload("u1")),
      "POST /api/v1/documents": () => json(201, makeDocument({ id: "d1" }), { ETag: '"v1"' }),
    });
    const { user, onSaved, onClose } = setup([pdfFile()]);

    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    expect(await api.calls[0]?.json()).toEqual({
      original_name: "01-general-blood-test.pdf",
      size_bytes: 79_114,
      content_type: "application/pdf",
    });
    expect([...FakeXhr.last.body!.keys()]).toEqual(["key", "policy", "file"]);
    act(() => FakeXhr.last.progress(62));
    expect(screen.getByText("79 КБ · загружено 62%")).toBeInTheDocument();
    act(() => FakeXhr.last.succeed());
    expect(await screen.findByText("Готов к сохранению")).toBeInTheDocument();

    const title = screen.getByLabelText("Название");
    expect(title).toHaveValue("General blood test");
    await user.clear(title);
    await user.type(title, "Общий анализ крови");
    await fillValidFields(user);
    await user.click(saveButton());

    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    const create = api.calls.find((call) => call.url.endsWith("/api/v1/documents"))!;
    expect(create.headers.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/);
    expect(await create.json()).toEqual({
      upload_id: "u1",
      title: "Общий анализ крови",
      type: "analysis",
      document_date: "2026-04-08",
    });
    expect(onClose).toHaveBeenCalledOnce();
  });

  test("TC-012: empty title blocks saving with a reason; Enter shows the error and sends nothing", async () => {
    const api = mockApi({ "POST /api/v1/uploads": () => json(201, upload("u1")) });
    const { user } = setup([pdfFile()]);
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    act(() => FakeXhr.last.succeed());

    const title = screen.getByLabelText("Название");
    await user.clear(title);

    expect(saveButton()).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Заполните название, чтобы сохранить")).toBeInTheDocument();

    await user.type(title, "{Enter}");

    expect(await screen.findByText("Введите название документа")).toBeInTheDocument();
    expect(title).toHaveFocus();
    expect(api.calls.some((call) => call.url.endsWith("/api/v1/documents"))).toBe(false);
  });

  test("TC-013 and TC-014: 31.02 and tomorrow are rejected before any request", async () => {
    const api = mockApi({ "POST /api/v1/uploads": () => json(201, upload("u1")) });
    const { user } = setup([pdfFile()]);
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    act(() => FakeXhr.last.succeed());
    await user.click(screen.getByRole("radio", { name: "Анализ" }));
    const date = screen.getByLabelText("Дата документа");

    await user.type(date, "31022026");
    await user.click(saveButton());
    expect(await screen.findByText("Такой даты нет. Проверьте день и месяц")).toBeInTheDocument();
    expect(date).toHaveFocus();

    await user.clear(date);
    await user.type(date, "11112026");
    await user.click(saveButton());
    expect(
      await screen.findByText("Дата документа не может быть позже сегодняшней"),
    ).toBeInTheDocument();
    expect(api.calls.some((call) => call.url.endsWith("/api/v1/documents"))).toBe(false);
  });

  test("TC-015: a PNG named .pdf is refused on the client without any request", async () => {
    const api = mockApi({});
    const png = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a])], "fake.pdf", {
      type: "application/pdf",
    });
    setup([png]);

    expect(await screen.findByText("Это не PDF")).toBeInTheDocument();
    expect(
      screen.getByText("Файл не добавлен: это не PDF. Сохраните документ в PDF и попробуйте снова"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Выбрать другой файл" })).toBeInTheDocument();
    expect(api.calls).toHaveLength(0);
    expect(FakeXhr.instances).toHaveLength(0);
  });

  test("TC-016: over 20 МБ is refused before the transfer", async () => {
    const api = mockApi({});
    setup([pdfFile("big-21mb.pdf", MAX_UPLOAD_BYTES + 1)]);

    expect(
      await screen.findByText("Файл больше 20 МБ. Сожмите PDF или разделите его на части"),
    ).toBeInTheDocument();
    expect(api.calls).toHaveLength(0);
    expect(FakeXhr.instances).toHaveLength(0);
  });

  test("TC-020: a break at 62% keeps the fields; retry gets a new upload_id and saves without re-entry", async () => {
    const uploads = ["u1", "u2"];
    const api = mockApi({
      "POST /api/v1/uploads": () => json(201, upload(uploads.shift()!)),
      "POST /api/v1/documents": () => json(201, makeDocument({ id: "d1" }), { ETag: '"v1"' }),
    });
    const { user, onSaved } = setup([pdfFile()]);
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    await fillValidFields(user);
    await user.click(saveButton());
    act(() => FakeXhr.last.progress(62));

    act(() => FakeXhr.last.onerror?.());

    expect(await screen.findByText("Связь прервалась на 62%")).toBeInTheDocument();
    expect(screen.getByLabelText("Название")).toHaveValue("General blood test");
    expect(screen.getByLabelText("Дата документа")).toHaveValue("08.04.2026");

    await user.click(screen.getByRole("button", { name: "Повторить загрузку" }));
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(2));
    act(() => FakeXhr.last.succeed());

    await waitFor(() => expect(onSaved).toHaveBeenCalledOnce());
    const create = api.calls.find((call) => call.url.endsWith("/api/v1/documents"))!;
    expect(await create.json()).toMatchObject({
      upload_id: "u2",
      type: "analysis",
      document_date: "2026-04-08",
    });
  });

  test("TC-021: Esc with typed input asks first; without input the form closes at once", async () => {
    mockApi({ "POST /api/v1/uploads": () => json(201, upload("u1")) });
    const { user, onClose } = setup([pdfFile()]);
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));

    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledOnce();
  });

  test("TC-021: typed input turns Esc into «Закрыть без сохранения?»", async () => {
    mockApi({ "POST /api/v1/uploads": () => json(201, upload("u1")) });
    const { user, onClose } = setup([pdfFile()]);
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    await user.type(screen.getByLabelText("Название"), " 2");

    await user.keyboard("{Escape}");

    expect(await screen.findByText("Закрыть без сохранения?")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Продолжить заполнение" }));
    expect(screen.getByLabelText("Название")).toHaveValue("General blood test 2");
  });

  test("closing the dialog mid-transfer aborts the storage upload", async () => {
    mockApi({ "POST /api/v1/uploads": () => json(201, upload("u1")) });
    const { unmount } = render(
      <Wrapper client={makeQueryClient()}>
        <UploadDialog initialFiles={[pdfFile()]} onSaved={vi.fn()} onClose={vi.fn()} />
      </Wrapper>,
    );
    await waitFor(() => expect(FakeXhr.instances).toHaveLength(1));
    act(() => FakeXhr.last.progress(40));
    const abort = vi.spyOn(FakeXhr.last, "abort");

    unmount();

    expect(abort).toHaveBeenCalledOnce();
  });

  test("several files go one by one: «Файл 1 из 2», «Сохранить и следующий»", async () => {
    mockApi({ "POST /api/v1/uploads": () => json(201, upload("u1")) });
    setup([pdfFile("01-a.pdf"), pdfFile("02-b.pdf")]);

    expect(await screen.findByText("Файл 1 из 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Сохранить и следующий" })).toBeInTheDocument();
  });
});
