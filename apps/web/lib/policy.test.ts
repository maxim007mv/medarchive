import { readFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "vitest";

import { policyMarkdown, policyVersion } from "./policy";

test("lib/policy.ts carries docs/policy.md byte for byte (run scripts/gen-policy.mjs)", () => {
  // Vitest runs from apps/web.
  const source = readFileSync(join(process.cwd(), "../../docs/policy.md"), "utf8");

  expect(policyMarkdown).toBe(source);
});

test("policy version is the one the consent fingerprint uses", () => {
  expect(policyVersion).toBe("2026-11-10");
});
