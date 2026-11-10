import { test as base } from "@playwright/test";

import { createArchive, SESSION_COOKIE, type Archive } from "./archive";

/** «Сейчас» of every test (TZ-qa, section 3): 10.11.2026 12:00 Europe/Moscow. */
export const FIXED_NOW = new Date("2026-11-10T12:00:00+03:00");

interface Fixtures {
  /** Page clock; `test.use({ clockTime: null })` keeps the real clock (day-boundary cases). */
  clockTime: Date | null;
  fixedClock: void;
  /** A new archive owned by this test only; the browser context already holds its session. */
  freshArchive: Archive;
}

export const test = base.extend<Fixtures>({
  clockTime: [FIXED_NOW, { option: true }],
  fixedClock: [
    async ({ page, clockTime }, use) => {
      // Fixed `Date`, running timers: debounce, autosave and toasts still fire.
      if (clockTime) await page.clock.setFixedTime(clockTime);
      await use();
    },
    { auto: true },
  ],
  freshArchive: async ({ context }, use) => {
    const archive = await createArchive(context.request);
    const cookies = await context.cookies();
    if (!cookies.some((cookie) => cookie.name === SESSION_COOKIE)) {
      // ADR-048 risk: the browser refused the Secure `__Host-` cookie on http://localhost.
      throw new Error(`${SESSION_COOKIE} was not stored by the browser context`);
    }
    await use(archive);
  },
});

export { expect } from "@playwright/test";
