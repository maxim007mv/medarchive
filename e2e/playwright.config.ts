import { defineConfig, devices } from "@playwright/test";

const resultsDir = process.env.E2E_RESULTS_DIR ?? "test-results";

// Runs against the compose stack (`make up`), not a dev server.
// Tests carry tags: `@bN` is the block that ships the feature (the gate of block N runs `@b1..@bN`),
// `@P0`/`@P1` the priority and `@TC-xxx` the case from MedArchive/05_qa/test-cases.md.
export default defineConfig({
  testDir: "./tests",
  outputDir: `${resultsDir}/artifacts`,
  forbidOnly: Boolean(process.env.CI),
  reporter: [
    ["list"],
    ["junit", { outputFile: `${resultsDir}/junit.xml` }],
    ["json", { outputFile: `${resultsDir}/report.json` }],
    ["html", { open: "never", outputFolder: `${resultsDir}/html` }],
  ],
  snapshotPathTemplate: "{testDir}/{testFileDir}/__snapshots__/{projectName}-{platform}/{arg}{ext}",
  expect: {
    // TC-115: less than 0.1% of pixels may differ from the application's own baseline.
    toHaveScreenshot: { maxDiffPixelRatio: 0.001, animations: "disabled", caret: "hide", scale: "css" },
  },
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    locale: "ru-RU",
    timezoneId: "Europe/Moscow",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    // Black-box contract checks need no browser and run once.
    { name: "api", testMatch: /\.api\.spec\.ts$/ },
    {
      name: "chromium-desktop",
      testIgnore: /\.api\.spec\.ts$/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "webkit-iphone13",
      testIgnore: /\.api\.spec\.ts$/,
      use: { ...devices["iPhone 13"] },
    },
  ],
});
