import { randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

import { expectStatus, POLICY_VERSION, SESSION_COOKIE } from "../../support/archive";

test("TC-003 workspace without consent is rejected and sets no cookie", { tag: ["@b3", "@P0", "@TC-003"] }, async ({ request }) => {
  const response = await request.post("/api/v1/workspaces", {
    headers: { "Idempotency-Key": randomUUID() },
    data: { consent: { policy_version: POLICY_VERSION, accepted: false }, timezone: "Europe/Moscow" },
  });

  await expectStatus(response, 422);
  const problem = (await response.json()) as { code: string; errors?: { pointer: string }[] };
  expect(problem.code).toBe("validation_error");
  expect(problem.errors?.map((error) => error.pointer)).toContain("/consent/accepted");
  expect(response.headers()["set-cookie"]).toBeUndefined();
  expect((await request.storageState()).cookies).toEqual([]);
});

// SEC-03 (T1, T14, ADR-047): the session cookie is unreadable from JS and not sent cross-site.
test("SEC-03 session cookie is __Host-, HttpOnly, Secure, SameSite=Lax", { tag: ["@b3", "@TC-002"] }, async ({ request }) => {
  const response = await request.post("/api/v1/workspaces", {
    headers: { "Idempotency-Key": randomUUID() },
    data: { consent: { policy_version: POLICY_VERSION, accepted: true }, timezone: "Europe/Moscow" },
  });

  await expectStatus(response, 201);
  const cookie = response.headers()["set-cookie"] ?? "";
  expect(cookie.startsWith(`${SESSION_COOKIE}=`)).toBe(true);
  expect(cookie).toMatch(/;\s*HttpOnly/i);
  expect(cookie).toMatch(/;\s*Secure/i);
  expect(cookie).toMatch(/;\s*SameSite=Lax/i);
  expect(cookie).toMatch(/;\s*Path=\//i);
  expect(cookie).not.toMatch(/;\s*Domain=/i);
  expect(response.headers()["cache-control"]).toBe("no-store");
});
