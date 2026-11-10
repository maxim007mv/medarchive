import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import { HomeScreen } from "./HomeScreen";
import { FakeXhr, json, makeQueryClient, mockApi, pdfFile, problem, Wrapper } from "./test-utils";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

function renderHome() {
  render(
    <Wrapper client={makeQueryClient()}>
      <HomeScreen />
    </Wrapper>,
  );
  return userEvent.setup();
}

afterEach(() => vi.unstubAllGlobals());

describe("onboarding (FE-11)", () => {
  test("TC-001: no session shows D01 with the pick button locked until consent", async () => {
    mockApi({ "GET /api/v1/session": () => problem(401, "unauthenticated", "Сессия закончилась") });
    const user = renderHome();

    expect(
      await screen.findByRole("heading", { name: "Все медицинские документы в одном месте" }),
    ).toBeInTheDocument();
    const pick = screen.getByRole("button", { name: "Выбрать первый PDF" });
    expect(pick).toHaveAttribute("aria-disabled", "true");
    expect(pick).toHaveAccessibleDescription("Отметьте согласие, чтобы выбрать файл");
    expect(
      screen.getByRole("link", { name: "Политика обработки персональных данных" }),
    ).toHaveAttribute("href", "/policy");
    expect(screen.getByRole("link", { name: "Уже есть архив? Открыть по ключу" })).toHaveAttribute(
      "href",
      "/restore",
    );

    await user.click(screen.getByRole("checkbox"));

    expect(pick).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByText("Отметьте согласие, чтобы выбрать файл")).not.toBeInTheDocument();
  });

  test("TC-002: the first file creates the archive with the consent, then the form opens", async () => {
    FakeXhr.install();
    const api = mockApi({
      "GET /api/v1/session": () => problem(401, "unauthenticated", "Сессия закончилась"),
      "POST /api/v1/workspaces": () =>
        json(201, {
          workspace: { id: "w1", created_at: "2026-11-10T09:00:00Z", document_count: 0 },
          access_key: "7K3M-Q9TB-2XRA-HC4D-P8WN-6YFE",
          csrf_token: "csrf-new",
          scopes: ["documents:read", "documents:write", "exports:create", "workspace:manage"],
        }),
      "GET /api/v1/documents": () =>
        json(200, { items: [], total: 0, matched: 0, undated_excluded: 0, next_page_token: "" }),
      "POST /api/v1/uploads": () =>
        json(201, {
          upload_id: "u1",
          url: "http://localhost:9000/q",
          fields: {},
          max_bytes: 1,
          expires_at: "2026-11-10T09:15:00Z",
        }),
    });
    const user = renderHome();
    await user.click(await screen.findByRole("checkbox"));

    await user.upload(screen.getByTestId("onboarding-file-input"), pdfFile());

    expect(await screen.findByRole("dialog", { name: "Новый документ" })).toBeInTheDocument();
    const created = api.calls.find((call) => call.url.endsWith("/api/v1/workspaces"))!;
    expect(created.headers.get("Idempotency-Key")).toBeTruthy();
    expect(await created.json()).toMatchObject({
      consent: { policy_version: "2026-11-10", accepted: true },
    });
    await waitFor(() =>
      expect(api.calls.some((call) => call.url.endsWith("/api/v1/uploads"))).toBe(true),
    );
    expect(
      api.calls.find((call) => call.url.endsWith("/api/v1/uploads"))?.headers.get("X-CSRF-Token"),
    ).toBe("csrf-new");
  });

  test("TC-015: a non-PDF first file is refused and no archive is created", async () => {
    const api = mockApi({
      "GET /api/v1/session": () => problem(401, "unauthenticated", "Сессия закончилась"),
    });
    const user = renderHome();
    await user.click(await screen.findByRole("checkbox"));
    const png = new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], "fake.pdf", {
      type: "application/pdf",
    });

    await user.upload(screen.getByTestId("onboarding-file-input"), png);

    expect(
      await screen.findByText(
        "Файл не добавлен: это не PDF. Сохраните документ в PDF и попробуйте снова",
      ),
    ).toBeInTheDocument();
    expect(api.calls.map((call) => new URL(call.url).pathname)).toEqual(["/api/v1/session"]);
  });

  test("an unreachable server shows «Не удаётся открыть архив» with «Повторить»", async () => {
    mockApi({ "GET /api/v1/session": () => Promise.reject(new TypeError("Failed to fetch")) });
    renderHome();

    expect(
      await screen.findByRole("heading", { name: "Не удаётся открыть архив" }, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Повторить" })).toBeInTheDocument();
  });
});
