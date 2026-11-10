import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";

import { DEFAULT_FILTERS, type DocumentFilters } from "@/lib/filters";

import { EmptySearch } from "./EmptySearch";

function renderEmpty(patch: Partial<DocumentFilters>) {
  const handlers = { onResetSearch: vi.fn(), onRemoveDates: vi.fn(), onResetAll: vi.fn() };
  render(<EmptySearch filters={{ ...DEFAULT_FILTERS, ...patch }} {...handlers} />);
  return { handlers, buttons: buttonNames() };
}

/** Accessible names of the buttons in DOM order (the Button label is doubled for its loading layer). */
function buttonNames(): string[] {
  const candidates = ["Сбросить поиск", "Убрать фильтр по дате", "Сбросить всё"];
  const all = screen.getAllByRole("button");
  return candidates
    .flatMap((name) =>
      screen
        .queryAllByRole("button", { name })
        .map((button) => ({ name, index: all.indexOf(button) })),
    )
    .sort((a, b) => a.index - b.index)
    .map(({ name }) => name);
}

describe("EmptySearch (FE-15)", () => {
  test("only a query: one «Сбросить поиск» (TC-033)", async () => {
    const { handlers, buttons } = renderEmpty({ q: "рентген" });

    expect(screen.getByRole("heading", { name: "Ничего не нашлось" })).toBeInTheDocument();
    expect(
      screen.getByText(
        "По запросу «рентген» документов нет. Проверьте название или сбросьте поиск.",
      ),
    ).toBeInTheDocument();
    expect(buttons).toEqual(["Сбросить поиск"]);

    await userEvent.click(screen.getByRole("button", { name: "Сбросить поиск" }));
    expect(handlers.onResetSearch).toHaveBeenCalledOnce();
  });

  test("query and period: «Убрать фильтр по дате» and «Сбросить всё» (D08)", async () => {
    const { handlers, buttons } = renderEmpty({
      q: "рентген",
      date_field: "uploaded",
      from: "2026-01-01",
      to: "2026-03-31",
    });

    expect(
      screen.getByText(
        "По запросу «рентген» за 01.01.2026 – 31.03.2026 документов нет. Попробуйте другое название или расширьте период.",
      ),
    ).toBeInTheDocument();
    expect(buttons).toEqual(["Убрать фильтр по дате", "Сбросить всё"]);

    await userEvent.click(screen.getByRole("button", { name: "Убрать фильтр по дате" }));
    await userEvent.click(screen.getByRole("button", { name: "Сбросить всё" }));
    expect(handlers.onRemoveDates).toHaveBeenCalledOnce();
    expect(handlers.onResetAll).toHaveBeenCalledOnce();
  });

  test("only a start date: the period text with a capital and both buttons", () => {
    const { buttons } = renderEmpty({ from: "2026-12-01" });

    expect(
      screen.getByText("С 01.12.2026 документов нет. Расширьте период или сбросьте фильтр."),
    ).toBeInTheDocument();
    expect(buttons).toEqual(["Убрать фильтр по дате", "Сбросить всё"]);
  });

  test("only a type: «Сбросить всё»", () => {
    const { buttons } = renderEmpty({ type: ["other"] });

    expect(
      screen.getByText("Документов с типом «Другое» нет. Сбросьте фильтр."),
    ).toBeInTheDocument();
    expect(buttons).toEqual(["Сбросить всё"]);
  });

  test("query with a type is not «only a query»", () => {
    expect(renderEmpty({ q: "рентген", type: ["analysis"] }).buttons).toEqual(["Сбросить всё"]);
  });

  test("a reversed range is not applied, so it does not count as dates", () => {
    expect(renderEmpty({ q: "рентген", from: "2026-04-30", to: "2026-04-01" }).buttons).toEqual([
      "Сбросить поиск",
    ]);
  });
});
