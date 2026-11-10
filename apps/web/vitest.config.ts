import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL(".", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    coverage: {
      provider: "v8",
      include: ["lib/**/*.ts"],
      exclude: ["lib/api/schema.d.ts", "lib/**/*.test.ts"],
      // TZ-frontend §8: lib/ coverage at least 90%.
      thresholds: { lines: 90, functions: 90, branches: 90, statements: 90 },
    },
  },
});
