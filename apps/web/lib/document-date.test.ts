import { describe, expect, test } from "vitest";

import { dateFromFileName, dateFromPdfText, guessDocumentDate } from "./document-date";

const TODAY = "2026-11-10";

function pdf(name: string, body: string, padding = 0): File {
  const text = `%PDF-1.4\n${" ".repeat(padding)}${body}`;
  return new File([new TextEncoder().encode(text)], name, { type: "application/pdf" });
}

describe("TC-118 date from the file name", () => {
  test.each([
    ["2026-04-08_obshchiy-analiz-krovi.pdf", "2026-04-08"],
    ["analiz_2026_04_08.pdf", "2026-04-08"],
    ["2026.04.08.pdf", "2026-04-08"],
    ["Анализ крови 08.04.2026.pdf", "2026-04-08"],
    ["08-04-2026 терапевт.pdf", "2026-04-08"],
    ["08_04_2026.PDF", "2026-04-08"],
    ["scan20260408.pdf", "2026-04-08"],
    ["20260408.pdf", "2026-04-08"],
    ["приём 08.04.26.pdf", "2026-04-08"],
    ["ЭКГ 15.03.98.pdf", "1998-03-15"],
    ["2026-11-10.pdf", "2026-11-10"],
    ["1900-01-01.pdf", "1900-01-01"],
  ])("%s → %s", (name, expected) => {
    expect(dateFromFileName(name, TODAY)).toBe(expected);
  });

  test.each([
    ["01-general-blood-test.pdf", "no date at all"],
    ["2026-11-11.pdf", "tomorrow"],
    ["15.12.26.pdf", "later this year"],
    ["31.02.2026.pdf", "no such day"],
    ["2026-13-01.pdf", "no such month"],
    ["1899-12-31.pdf", "before 1900"],
    ["scan_1234567890.pdf", "digits of a longer number"],
    ["120260408.pdf", "eight digits inside nine"],
    ["2026-04-081.pdf", "a day glued to another digit"],
    ["v1.2.3.pdf", "a version number"],
  ])("%s gives nothing: %s", (name) => {
    expect(dateFromFileName(name, TODAY)).toBeNull();
  });

  test("the first valid date wins when the first one in the name is not", () => {
    expect(dateFromFileName("31.02.2026 повтор 03.03.2026.pdf", TODAY)).toBe("2026-03-03");
  });

  test("a full date is preferred over a short one", () => {
    expect(dateFromFileName("05.05.25 сдан 2026-04-08.pdf", TODAY)).toBe("2026-04-08");
  });
});

describe("TC-118 date from /CreationDate", () => {
  test.each([
    ["/CreationDate (D:20260410093000+03'00')", "2026-04-10"],
    ["/CreationDate(D:20260410)", "2026-04-10"],
    ["/Producer (x) /CreationDate ( D:19991231235959Z)", "1999-12-31"],
    ["/CreationDate (D:20260101093000)", "2026-01-01"],
  ])("%s → %s", (text, expected) => {
    expect(dateFromPdfText(text, TODAY)).toBe(expected);
  });

  test.each([
    ["/ModDate (D:20260410093000)", "only a modification date"],
    ["/CreationDate (D:2026)", "year only"],
    ["/CreationDate (D:20261231)", "in the future"],
    ["/CreationDate (D:20260231)", "no such day"],
    ["/CreationDate (D:18991231)", "before 1900"],
    ["/CreationDate <FEFF0044003A>", "a hex string"],
    ["/CreationDate (D:20000101000000+00'00')", "the placeholder of the task fixtures"],
    ["/CreationDate (D:20260101)", "1 January without a time"],
  ])("%s gives nothing: %s", (text) => {
    expect(dateFromPdfText(text, TODAY)).toBeNull();
  });
});

describe("TC-118 guessDocumentDate", () => {
  test("the file name comes before the PDF properties", async () => {
    const file = pdf("2026-04-08_analiz.pdf", "/CreationDate (D:20260410)");

    expect(await guessDocumentDate(file, TODAY)).toEqual({
      date: "2026-04-08",
      source: "fileName",
    });
  });

  test("without a date in the name the PDF properties are read", async () => {
    const file = pdf("analiz.pdf", "/CreationDate (D:20260410093000+03'00')");

    expect(await guessDocumentDate(file, TODAY)).toEqual({ date: "2026-04-10", source: "pdf" });
  });

  test("an Info dictionary at the end of a file over 1 MiB is found", async () => {
    const file = pdf("analiz.pdf", "/CreationDate (D:20260410)", 3 * 1024 * 1024);

    expect(await guessDocumentDate(file, TODAY)).toEqual({ date: "2026-04-10", source: "pdf" });
  });

  test("an invalid name date falls through to the PDF properties", async () => {
    const file = pdf("31.02.2026.pdf", "/CreationDate (D:20260410)");

    expect(await guessDocumentDate(file, TODAY)).toEqual({ date: "2026-04-10", source: "pdf" });
  });

  test("nothing to go on gives null", async () => {
    expect(await guessDocumentDate(pdf("analiz.pdf", "1 0 obj"), TODAY)).toBeNull();
  });
});
