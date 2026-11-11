import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

import { BackLink } from "./BackLink";
import { LIST_URL_KEY } from "./list-url";
import { json, makeQueryClient, mockApi, problem, Wrapper } from "./test-utils";

function renderBackLink() {
  render(
    <Wrapper client={makeQueryClient()}>
      <BackLink />
    </Wrapper>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("TC-116 back link", () => {
  test("with an archive it leads to the list with the filters it was left with", async () => {
    sessionStorage.setItem(LIST_URL_KEY, "/?q=%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D0%B7");
    mockApi({
      "GET /api/v1/session": () =>
        json(200, { workspace_id: "w1", csrf_token: "c", scopes: [], timezone: "UTC" }),
    });
    renderBackLink();

    expect(await screen.findByRole("link", { name: "К документам" })).toHaveAttribute(
      "href",
      "/?q=%D0%B0%D0%BD%D0%B0%D0%BB%D0%B8%D0%B7",
    );
  });

  test("with an archive but no list visited in this tab it leads to /", async () => {
    mockApi({
      "GET /api/v1/session": () =>
        json(200, { workspace_id: "w1", csrf_token: "c", scopes: [], timezone: "UTC" }),
    });
    renderBackLink();

    expect(await screen.findByRole("link", { name: "К документам" })).toHaveAttribute("href", "/");
  });

  test("before there is an archive it leads to the start page", async () => {
    sessionStorage.setItem(LIST_URL_KEY, "/?q=old");
    mockApi({ "GET /api/v1/session": () => problem(401, "unauthenticated", "Сессия закончилась") });
    renderBackLink();

    expect(await screen.findByRole("link", { name: "На главную" })).toHaveAttribute("href", "/");
  });

  test("stays out of the accessibility tree until the session is known", () => {
    mockApi({ "GET /api/v1/session": () => new Promise<Response>(() => undefined) });
    renderBackLink();

    expect(screen.getByText("На главную").closest("a")).toHaveClass("invisible");
  });
});
