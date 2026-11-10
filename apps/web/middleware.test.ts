// @vitest-environment node
import { NextRequest } from "next/server";
import { expect, test } from "vitest";

import { config, middleware } from "./middleware";

function directives(csp: string): Map<string, string> {
  return new Map(
    csp.split("; ").map((directive) => {
      const [name = "", ...values] = directive.split(" ");
      return [name, values.join(" ")];
    }),
  );
}

test("OPS-06: page responses carry CSP with a fresh nonce and the security headers", () => {
  const first = middleware(new NextRequest("http://localhost/"));
  const second = middleware(new NextRequest("http://localhost/"));

  const csp = directives(first.headers.get("Content-Security-Policy") ?? "");
  expect(csp.get("default-src")).toBe("'self'");
  expect(csp.get("script-src")).toMatch(/^'self' 'nonce-[A-Za-z0-9+/=]{40,}'$/);
  expect(csp.get("frame-ancestors")).toBe("'none'");
  expect(csp.get("object-src")).toBe("'none'");
  expect(csp.get("frame-src")).toBe("'self'");
  expect(first.headers.get("Referrer-Policy")).toBe("no-referrer");
  expect(first.headers.get("Permissions-Policy")).toBe("camera=(), geolocation=(), microphone=()");
  expect(first.headers.get("X-Content-Type-Options")).toBe("nosniff");
  expect(second.headers.get("Content-Security-Policy")).not.toBe(
    first.headers.get("Content-Security-Policy"),
  );
});

test("OPS-06: the nonce reaches the app through the request headers", () => {
  const response = middleware(new NextRequest("http://localhost/"));

  const csp = response.headers.get("Content-Security-Policy") ?? "";
  const nonce = /'nonce-([^']+)'/.exec(csp)?.[1];
  expect(nonce).toBeTruthy();
  expect(response.headers.get("x-middleware-request-x-nonce")).toBe(nonce);
});

test("OPS-06: API and static paths are not matched", () => {
  const [pattern = ""] = config.matcher;
  const matches = (path: string) => new RegExp(`^${pattern}$`).test(path);

  expect(matches("/")).toBe(true);
  expect(matches("/documents/1")).toBe(true);
  expect(matches("/api/v1/session")).toBe(false);
  expect(matches("/_next/static/chunk.js")).toBe(false);
});
