import { defineConfig } from "@playwright/test";

const liveBase = (process.env.LIVE_BASE_URL || "").replace(/\/?$/, "/");

export default defineConfig({
  testDir: ".",
  testMatch: "live.spec.js",
  fullyParallel: false,
  workers: 1,
  retries: 2,
  reporter: process.env.CI ? "line" : "list",
  use: {
    baseURL: liveBase,
    viewport: { width: 1280, height: 900 },
    trace: "retain-on-failure",
  },
});
