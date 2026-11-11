import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import { DEFAULT_FILTERS, type DocumentFilters } from "@/lib/filters";

import { defaultExportScope, ExportDialog } from "./ExportDialog";
import { json, makeQueryClient, mockApi, Wrapper } from "./test-utils";

const exportOf = (body: { scope: string }, total_bytes: number) => ({
  id: "e1",
  scope: body.scope,
  document_count: 2,
  total_bytes,
  content_url: `/api/v1/exports/e-${body.scope}/content`,
  expires_at: "2026-11-10T17:31:00Z",
});

function setup({
  filters = DEFAULT_FILTERS,
  selectedIds = [] as string[],
}: {
  filters?: DocumentFilters;
  selectedIds?: string[];
}) {
  const bytes: Record<string, number> = { all: 466_000, filtered: 157_224, selected: 79_114 };
  const api = mockApi({
    "POST /api/v1/exports": async (request) => {
      const body = await request.json();
      return json(201, exportOf(body, bytes[body.scope]!));
    },
  });
  const filtered = filters !== DEFAULT_FILTERS;
  render(
    <Wrapper client={makeQueryClient()}>
      <ExportDialog
        filters={filters}
        filtered={filtered}
        total={6}
        matched={2}
        selectedIds={selectedIds}
        onClose={vi.fn()}
      />
    </Wrapper>,
  );
  return { api, user: userEvent.setup() };
}

afterEach(() => vi.unstubAllGlobals());

describe("ExportDialog (FE-20)", () => {
  test("default scope follows the filter", () => {
    expect(defaultExportScope(true)).toBe("filtered");
    expect(defaultExportScope(false)).toBe("all");
  });

  test("TC-071: with a search «Только найденные» is chosen and sized from total_bytes", async () => {
    const { api } = setup({ filters: { ...DEFAULT_FILTERS, q: "анализ" } });

    expect(screen.getByRole("radio", { name: "Только найденные" })).toBeChecked();
    expect(screen.getByText("2 документа по текущему поиску и фильтру")).toBeInTheDocument();
    const download = await screen.findByRole("link", { name: /^Скачать ZIP · 157\sКБ$/ });
    expect(download).toHaveAttribute("href", "/api/v1/exports/e-filtered/content");
    expect(await api.calls[0]?.json()).toEqual({ scope: "filtered", filter: { q: "анализ" } });
    expect(api.calls[0]?.headers.get("Idempotency-Key")).toBeTruthy();
  });

  test("TC-070: without filters «Весь архив» is chosen and «Только найденные» is unavailable", async () => {
    setup({});

    expect(screen.getByRole("radio", { name: "Весь архив" })).toBeChecked();
    expect(screen.getByText("6 документов")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Только найденные" })).toBeDisabled();
    expect(
      await screen.findByRole("link", { name: /^Скачать ZIP · 466\sКБ$/ }),
    ).toBeInTheDocument();
  });

  test("«Выбранные» is unavailable until rows are checked", () => {
    setup({});

    expect(screen.getByRole("radio", { name: "Выбранные" })).toBeDisabled();
    expect(screen.getByText("Отметьте документы в списке")).toBeInTheDocument();
  });

  test("checked rows enable «Выбранные», which exports exactly them", async () => {
    const { api, user } = setup({ selectedIds: ["d1"] });

    await user.click(screen.getByRole("radio", { name: "Выбранные" }));

    expect(await screen.findByRole("link", { name: /^Скачать ZIP · 79\sКБ$/ })).toBeInTheDocument();
    await waitFor(() => expect(api.calls).toHaveLength(2));
    expect(await api.calls[1]?.json()).toEqual({ scope: "selected", document_ids: ["d1"] });
  });
});
