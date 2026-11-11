import { describe, expect, test } from "vitest";

import {
  DEFAULT_FILTERS,
  type DocumentFilters,
  hasAppliedFilters,
  isIsoDay,
  loadFilters,
  serializeFilters,
  toExportFilter,
  toListQuery,
} from "./filters";

const filters = (patch: Partial<DocumentFilters>): DocumentFilters => ({
  ...DEFAULT_FILTERS,
  ...patch,
});

describe("URL round-trip (FE-14, TC-040)", () => {
  test.each<[string, Partial<DocumentFilters>]>([
    ["search", { q: "анализ" }],
    ["document date range", { date_field: "document", from: "2026-04-01", to: "2026-04-30" }],
    ["upload date from only", { date_field: "uploaded", from: "2026-11-10" }],
    ["several types", { type: ["analysis", "conclusion"] }],
    ["undated with search and type", { undated: true, q: "экг", type: ["conclusion"] }],
    ["order by upload", { order_by: "uploaded_at desc" }],
  ])("%s survives serialize and load", (_, patch) => {
    const url = serializeFilters("/", filters(patch));

    const loaded = loadFilters(new URL(url, "http://localhost").searchParams);

    expect(loaded).toEqual(filters(patch));
  });

  test("defaults leave the URL clean", () => {
    expect(serializeFilters("/", DEFAULT_FILTERS)).toBe("/");
  });

  test("dates stay ISO in the URL", () => {
    const url = serializeFilters("/", filters({ from: "2026-04-01", to: "2026-04-30" }));

    expect(url).toBe("/?from=2026-04-01&to=2026-04-30");
  });

  test("garbage in the URL falls back to defaults", () => {
    const loaded = loadFilters(
      new URLSearchParams(
        "date_field=x&from=2026-02-31&to=31.04.2026&type=xray&order_by=title&undated=maybe",
      ),
    );

    expect(loaded).toEqual(DEFAULT_FILTERS);
  });
});

describe("isIsoDay", () => {
  test.each([
    ["2026-04-08", true],
    ["2028-02-29", true],
    ["2026-02-29", false],
    ["2026-02-31", false],
    ["2026-4-8", false],
    ["08.04.2026", false],
  ])("%s → %s", (value, expected) => {
    expect(isIsoDay(value)).toBe(expected);
  });
});

describe("toListQuery", () => {
  test("no filters sends nothing", () => {
    expect(toListQuery(DEFAULT_FILTERS, "Europe/Moscow")).toEqual({});
  });

  test("queries shorter than 3 characters are not sent (TC-032)", () => {
    expect(toListQuery(filters({ q: " а н " }), "Europe/Moscow")).toEqual({});
  });

  test("search is trimmed", () => {
    expect(toListQuery(filters({ q: "  анализ " }), "Europe/Moscow")).toEqual({ q: "анализ" });
  });

  test("document date range goes with its field and no zone", () => {
    expect(toListQuery(filters({ from: "2026-04-01", to: "2026-04-30" }), "Europe/Moscow")).toEqual(
      {
        date_field: "document",
        from: "2026-04-01",
        to: "2026-04-30",
      },
    );
  });

  test("upload date range carries the zone for day boundaries (TC-044b)", () => {
    expect(
      toListQuery(
        filters({ date_field: "uploaded", from: "2026-11-10", to: "2026-11-10" }),
        "Europe/Moscow",
      ),
    ).toEqual({
      date_field: "uploaded",
      from: "2026-11-10",
      to: "2026-11-10",
      tz: "Europe/Moscow",
    });
  });

  test("reversed range is not applied (TC-039)", () => {
    expect(toListQuery(filters({ from: "2026-04-30", to: "2026-04-01" }), "Europe/Moscow")).toEqual(
      {},
    );
  });

  test("undated keeps search and type and drops dates (TC-035)", () => {
    expect(
      toListQuery(
        filters({
          undated: true,
          q: "экг",
          type: ["conclusion"],
          from: "2026-04-01",
          to: "2026-04-30",
        }),
        "Europe/Moscow",
      ),
    ).toEqual({ undated: true, q: "экг", type: ["conclusion"] });
  });

  test("default order is implied", () => {
    expect(toListQuery(filters({ order_by: "uploaded_at desc" }), "UTC")).toEqual({
      order_by: "uploaded_at desc",
    });
  });
});

describe("hasAppliedFilters", () => {
  test.each<[string, Partial<DocumentFilters>, boolean]>([
    ["nothing", {}, false],
    ["short query", { q: "ан" }, false],
    ["query", { q: "анализ" }, true],
    ["only from", { from: "2026-04-01" }, true],
    ["reversed range", { from: "2026-04-30", to: "2026-04-01" }, false],
    ["type", { type: ["other"] }, true],
    ["undated", { undated: true }, true],
    ["order only", { order_by: "uploaded_at desc" }, false],
  ])("%s → %s", (_, patch, expected) => {
    expect(hasAppliedFilters(filters(patch))).toBe(expected);
  });
});

test("export filter repeats the list conditions without paging or order", () => {
  expect(
    toExportFilter(filters({ q: "анализ", from: "2026-04-01", order_by: "uploaded_at desc" })),
  ).toEqual({
    q: "анализ",
    date_field: "document",
    from: "2026-04-01",
  });
});
