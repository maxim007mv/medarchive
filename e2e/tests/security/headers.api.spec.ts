import { expect, test } from "@playwright/test";

// SEC-02: neither the web server nor the API names its software and version.
test("SEC-02 web and API responses do not reveal server software", { tag: ["@b1"] }, async ({ request }) => {
  for (const path of ["/", "/api/v1/session"]) {
    const headers = (await request.get(path)).headers();
    expect(headers["x-powered-by"], path).toBeUndefined();
    expect(headers.server, path).toBeUndefined();
  }
});

// OPS-06: the web page headers from TZ-devops-security; the theme script uses a nonce (block 2).
test("OPS-06 web pages send CSP, Referrer-Policy and Permissions-Policy", { tag: ["@b7"] }, async ({ request }) => {
  const headers = (await request.get("/")).headers();
  const csp = headers["content-security-policy"] ?? "";

  expect(csp).toContain("default-src 'self'");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).toContain("object-src 'none'");
  expect(csp).not.toMatch(/script-src[^;]*'unsafe-inline'/);
  expect(headers["referrer-policy"]).toBe("no-referrer");
  expect(headers["permissions-policy"]).toMatch(/camera=\(\)/);
  expect(headers["permissions-policy"]).toMatch(/geolocation=\(\)/);
  expect(headers["x-content-type-options"]).toBe("nosniff");
});

// BE-14: API responses are data, never a document the browser could render.
test("OPS-06 API responses send default-src 'none' and nosniff", { tag: ["@b7"] }, async ({ request }) => {
  const headers = (await request.get("/api/v1/session")).headers();

  expect(headers["content-security-policy"]).toContain("default-src 'none'");
  expect(headers["x-content-type-options"]).toBe("nosniff");
});
