// @vitest-environment node
import { readFileSync } from "node:fs";

import { expect, test } from "vitest";

import { DICTIONARY_PATH, OUTPUT_PATH, renderTexts } from "../scripts/gen-texts.mjs";
import { errorTitles, plurals, t, texts } from "./texts";

test("lib/texts.ts is generated from the current docs/texts.md", () => {
  const generated = renderTexts(readFileSync(DICTIONARY_PATH, "utf8"));

  expect(readFileSync(OUTPUT_PATH, "utf8"), "run `pnpm gen:texts`").toBe(generated);
});

test("dictionary follows the typography rules of docs/texts.md, section 1", () => {
  const all = [...Object.values(texts), ...Object.values(errorTitles)];

  expect(all.filter((text) => text.includes("\u2014"))).toEqual([]);
  expect(all.filter((text) => text.includes("..."))).toEqual([]);
});

test("placeholders are filled by name", () => {
  expect(t("chip.remove", { chip: "Поиск: анализ" })).toBe("Убрать фильтр «Поиск: анализ»");
  expect(t("upload.queue.position", { n: 1, total: 3 })).toBe("Файл 1 из 3");
  expect(t("common.cancel")).toBe("Отмена");
});

test("a missing value leaves its placeholder visible instead of «undefined»", () => {
  const params = {} as Parameters<typeof t<"chip.remove">>[1];

  expect(t("chip.remove", params)).toBe("Убрать фильтр «{chip}»");
});

test("all error codes of the catalog are present", () => {
  expect(Object.keys(errorTitles)).toHaveLength(32);
  expect(errorTitles.date_invalid).toBe("Такой даты нет. Проверьте день и месяц");
});

test("plural forms come from the dictionary table", () => {
  expect(plurals.документ).toEqual(["документ", "документа", "документов"]);
  expect(plurals.найден).toEqual(["Найден", "Найдено", "Найдено"]);
});
