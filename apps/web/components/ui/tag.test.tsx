import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { errorTitles, t, texts } from "@/lib/texts";

import { Alert } from "./alert";
import { seriousViolations } from "./axe";
import { Chip } from "./chip";
import { TypeTag, UndatedTag } from "./tag";

test("FE-09: type tags carry the word, not only the colour", () => {
  render(
    <div>
      <TypeTag type="analysis" />
      <TypeTag type="conclusion" />
      <TypeTag type="other" />
      <UndatedTag />
    </div>,
  );

  for (const label of [texts["type.analysis"], texts["type.conclusion"], texts["type.other"]]) {
    expect(screen.getByText(label)).toBeVisible();
  }
  expect(screen.getByText(texts["list.row.noDate"])).toBeVisible();
});

test("FE-09: the chip cross is named after the chip and removes it", async () => {
  const onRemove = vi.fn();
  const text = t("chip.documentDate.range", { from: "01.04.2026", to: "30.04.2026" });
  render(<Chip text={text} onRemove={onRemove} />);

  await userEvent.click(screen.getByRole("button", { name: t("chip.remove", { chip: text }) }));

  expect(onRemove).toHaveBeenCalledOnce();
  expect(screen.getByText("Дата документа:")).toBeVisible();
  expect(screen.getByText("01.04.2026 – 30.04.2026")).toBeVisible();
});

test("FE-09: a chip without a field shows the whole text as the value", () => {
  render(<Chip text={texts["chip.undated"]} onRemove={() => undefined} />);

  expect(screen.getByText(texts["chip.undated"])).toBeVisible();
});

test("FE-09: only the danger alert is announced as an alert", () => {
  render(
    <div>
      <Alert variant="danger" title={errorTitles.not_pdf} />
      <Alert variant="info">{t("undated.hint.one", { n: 1 })}</Alert>
      <Alert variant="warn" title={errorTitles.version_conflict} />
      <Alert variant="success">{texts["note.saved"]}</Alert>
    </div>,
  );

  expect(screen.getAllByRole("alert")).toHaveLength(1);
  expect(screen.getByRole("alert")).toHaveTextContent(errorTitles.not_pdf);
});

test("FE-09: tags, chips and alerts have no serious axe violations", async () => {
  const { container } = render(
    <div>
      <TypeTag type="analysis" />
      <UndatedTag />
      <Chip text={t("chip.search", { q: "анализ" })} onRemove={() => undefined} />
      <Alert variant="danger" title={errorTitles.not_pdf} />
      <Alert variant="info">{texts["export.zip.text"]}</Alert>
    </div>,
  );

  expect(await seriousViolations(container)).toEqual([]);
});
