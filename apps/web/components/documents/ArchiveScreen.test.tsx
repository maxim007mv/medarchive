import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, test, vi } from "vitest";

import type { DocumentItem } from "@/lib/api/queries";
import { formatDateTime } from "@/lib/format";

import { ArchiveScreen } from "./ArchiveScreen";
import { json, makeQueryClient, mockApi, Wrapper } from "./test-utils";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
// Every table row and every card formats its upload time once per render.
vi.mock("@/lib/format", async (importOriginal) => {
  const format = await importOriginal<typeof import("@/lib/format")>();
  return { ...format, formatDateTime: vi.fn(format.formatDateTime) };
});

const ROWS = 20;

function listItem(index: number): DocumentItem {
  return {
    id: `d${index}`,
    title: `Анализ ${index}`,
    type: "analysis",
    document_date: "2026-04-08",
    uploaded_at: "2026-11-10T16:02:11Z",
    has_note: false,
    size_bytes: 79_114,
    version: 1,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("ArchiveScreen list (FE-13)", () => {
  test("ticking one row re-renders that row only, not the rest of the list", async () => {
    const items = Array.from({ length: ROWS }, (_, index) => listItem(index));
    mockApi({
      "GET /api/v1/documents": () =>
        json(200, { items, total: ROWS, matched: ROWS, undated_excluded: 0, next_page_token: "" }),
    });
    render(
      <Wrapper client={makeQueryClient()}>
        <ArchiveScreen
          session={{ workspace_id: "w1", csrf_token: "c", scopes: [], timezone: "UTC" }}
          initialFiles={[]}
          onInitialFilesDone={() => undefined}
          issuedKey={null}
          onKeyShown={() => undefined}
        />
      </Wrapper>,
    );
    const user = userEvent.setup();
    const rows = await screen.findAllByTestId("document-row");
    expect(rows).toHaveLength(ROWS);
    vi.mocked(formatDateTime).mockClear();

    await user.click(within(rows[5]!).getByRole("checkbox"));

    expect(within(rows[5]!).getByRole("checkbox")).toBeChecked();
    expect(formatDateTime).toHaveBeenCalledTimes(1);
  });
});
