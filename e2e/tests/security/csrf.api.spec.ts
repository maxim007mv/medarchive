import { randomUUID } from "node:crypto";

import { expect, test, type APIResponse } from "@playwright/test";

import { createArchive, expectStatus } from "../../support/archive";

async function expectCsrfFailed(response: APIResponse): Promise<void> {
  await expectStatus(response, 403);
  expect(((await response.json()) as { code: string }).code).toBe("csrf_failed");
}

test.describe("TC-093 mutating requests require X-CSRF-Token", { tag: ["@b3", "@P0", "@TC-093"] }, () => {
  test("missing token", async ({ request }) => {
    await createArchive(request);

    await expectCsrfFailed(
      await request.post("/api/v1/workspace/access-key", { headers: { "Idempotency-Key": randomUUID() } }),
    );
    await expectCsrfFailed(await request.delete("/api/v1/sessions/current"));
  });

  test("token of another session", async ({ playwright, baseURL }) => {
    const first = await playwright.request.newContext({ baseURL });
    const second = await playwright.request.newContext({ baseURL });
    const foreign = await createArchive(first);
    await createArchive(second);

    await expectCsrfFailed(
      await second.post("/api/v1/workspace/access-key", {
        headers: { "Idempotency-Key": randomUUID(), "X-CSRF-Token": foreign.csrfToken },
      }),
    );
    await first.dispose();
    await second.dispose();
  });
});
