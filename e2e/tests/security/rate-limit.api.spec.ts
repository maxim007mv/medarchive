import { expect, test } from "@playwright/test";

import { createArchive, expectStatus } from "../../support/archive";
import { sources } from "../../support/manifest";

const UPLOADS_PER_MINUTE = 30;

test("TC-098 the 31st upload in a minute is 429 with Retry-After and RateLimit", { tag: ["@b7", "@P1", "@TC-098"] }, async ({ request }) => {
  const { api } = await createArchive(request);
  const body = { original_name: sources[0].fileName, size_bytes: sources[0].sizeBytes, content_type: "application/pdf" };

  for (let attempt = 1; attempt <= UPLOADS_PER_MINUTE; attempt += 1) {
    const allowed = await api.send("POST", "/api/v1/uploads", { data: body });
    await expectStatus(allowed, 201);
    expect(allowed.headers().ratelimit, `attempt ${attempt}`).toBeTruthy();
    expect(allowed.headers()["ratelimit-policy"]).toMatch(/q=30;\s*w=60/);
  }
  const limited = await api.send("POST", "/api/v1/uploads", { data: body });

  await expectStatus(limited, 429);
  expect(((await limited.json()) as { code: string }).code).toBe("rate_limited");
  expect(Number(limited.headers()["retry-after"])).toBeGreaterThan(0);
  expect(limited.headers().ratelimit).toBeTruthy();
});
