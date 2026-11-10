import { describe, expect, test } from "vitest";

import {
  formatDate,
  formatDateTime,
  formatSize,
  maskDate,
  parseDate,
  plural,
  titleFromFileName,
} from "./format";
import { plurals } from "./texts";

const NBSP = "\u00a0";

describe("plural", () => {
  test.each([
    [1, "документ"],
    [2, "документа"],
    [4, "документа"],
    [5, "документов"],
    [11, "документов"],
    [12, "документов"],
    [14, "документов"],
    [21, "документ"],
    [22, "документа"],
    [0, "документов"],
    [111, "документов"],
    [101, "документ"],
  ])("%i %s", (n, expected) => {
    expect(plural(n, plurals.документ)).toBe(expected);
  });
});

describe("formatSize", () => {
  test.each([
    [79_114, `79${NBSP}КБ`],
    [78_110, `78${NBSP}КБ`],
    [157_224, `157${NBSP}КБ`],
    [499, `1${NBSP}КБ`],
    [1, `1${NBSP}КБ`],
    [999_499, `999${NBSP}КБ`],
    [999_500, `1${NBSP}МБ`],
    [2_400_000, `2,4${NBSP}МБ`],
    [20_000_000, `20${NBSP}МБ`],
    [2_450_000, `2,5${NBSP}МБ`],
  ])("%i bytes → %s", (bytes, expected) => {
    expect(formatSize(bytes)).toBe(expected);
  });
});

describe("dates", () => {
  test("document date is printed as дд.мм.гггг", () => {
    expect(formatDate("2026-04-08")).toBe("08.04.2026");
  });

  test("upload moment is shown in Moscow time by default", () => {
    expect(formatDateTime("2026-11-10T16:02:00Z")).toBe("10.11.2026, 19:02");
  });

  test("upload just after midnight in Moscow belongs to the next day", () => {
    expect(formatDateTime("2026-11-10T21:30:00Z")).toBe("11.11.2026, 00:30");
  });

  test("upload moment follows the user's time zone", () => {
    expect(formatDateTime(new Date("2026-11-10T16:02:00Z"), "Asia/Yekaterinburg")).toBe(
      "10.11.2026, 21:02",
    );
  });
});

describe("titleFromFileName", () => {
  test.each([
    ["01-general-blood-test.pdf", "General blood test"],
    ["2026_05_21  lipidogramma.PDF", "Lipidogramma"],
    ["общий_анализ крови.pdf", "Общий анализ крови"],
    ["ЭКГ покоя", "ЭКГ покоя"],
    ["20260408.pdf", ""],
  ])("%s → «%s»", (fileName, expected) => {
    expect(titleFromFileName(fileName)).toBe(expected);
  });
});

describe("date input", () => {
  test.each([
    ["0", "0"],
    ["0804", "08.04"],
    ["08.04.2026", "08.04.2026"],
    ["080420261", "08.04.2026"],
    ["08a04", "08.04"],
  ])("mask %s → %s", (input, expected) => {
    expect(maskDate(input)).toBe(expected);
  });

  test.each([
    ["29.02.2028", "2028-02-29"],
    ["08.04.2026", "2026-04-08"],
    ["31.12.2025", "2025-12-31"],
  ])("TC FE-04: %s is a real date", (text, expected) => {
    expect(parseDate(text)).toBe(expected);
  });

  test.each(["31.02.2026", "29.02.2026", "00.01.2026", "15.13.2026", "08.04", "", "01.01.0026"])(
    "TC FE-04: %s is not a date",
    (text) => {
      expect(parseDate(text)).toBeNull();
    },
  );
});
