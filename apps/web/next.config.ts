import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

// Rewrites are resolved at build time, so the Docker image is built with API_ORIGIN=http://api:8000.
const apiOrigin = process.env.API_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  // The pnpm workspace root; without it Next guesses from lockfiles found above the repo.
  outputFileTracingRoot: fileURLToPath(new URL("../..", import.meta.url)),
  poweredByHeader: false,
  async rewrites() {
    // The browser talks to one origin; the session cookie and CSRF need no CORS (ADR-048).
    return [{ source: "/api/v1/:path*", destination: `${apiOrigin}/api/v1/:path*` }];
  },
};

export default nextConfig;
