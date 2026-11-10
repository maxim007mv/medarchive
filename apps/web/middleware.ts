import { NextResponse, type NextRequest } from "next/server";

// The browser uploads with presigned POST straight to object storage (FE-12), so its origin is
// the only one besides our own that scripts may connect to.
const storageOrigin = process.env.S3_PUBLIC_ENDPOINT ?? "http://localhost:9000";
// The dev server needs eval for React Refresh and injects CSS through <style> tags.
const isDev = process.env.NODE_ENV === "development";

export function contentSecurityPolicy(nonce: string): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}'${isDev ? " 'unsafe-eval'" : ""}`,
    `style-src 'self'${isDev ? " 'unsafe-inline'" : ""}`,
    `connect-src 'self' ${storageOrigin}`,
    // The PDF viewer is an iframe on /api/v1/documents/{id}/content (FE-16).
    "frame-src 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
  ].join("; ");
}

// OPS-06: the nonce lets the inline theme script run before paint (FE-01). Next.js reads it from
// the request CSP header and puts it on its own inline scripts.
export function middleware(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const csp = contentSecurityPolicy(nonce);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  response.headers.set("Referrer-Policy", "no-referrer");
  response.headers.set("Permissions-Policy", "camera=(), geolocation=(), microphone=()");
  response.headers.set("X-Content-Type-Options", "nosniff");
  return response;
}

export const config = {
  // API responses carry their own headers (PDFs get `CSP: sandbox`); static files need no nonce.
  matcher: ["/((?!api/|_next/static|_next/image|favicon.ico).*)"],
};
