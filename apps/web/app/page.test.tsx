import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import HomePage from "./page";

test("home page shows the product name as the main heading", () => {
  render(<HomePage />);

  expect(screen.getByRole("heading", { level: 1, name: "Медархив" })).toBeInTheDocument();
});
