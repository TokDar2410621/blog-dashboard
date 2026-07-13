import { defineConfig, devices } from "@playwright/test";
import * as dotenv from "dotenv";
import * as path from "path";

dotenv.config({ path: path.resolve(__dirname, ".env") });

const BASE_URL = process.env.E2E_BASE_URL || "https://gridar.app";

export default defineConfig({
  testDir: "./tests",
  // Prod target: run serially and be patient. We are hitting the live app.
  fullyParallel: false,
  workers: 1,
  retries: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    // 1. Authenticated setup: log in once, persist storage state.
    { name: "setup", testMatch: "**/auth.setup.ts" },
    // 2. Public flows that need NO auth (audit, landing pages, marketing).
    {
      name: "public",
      testMatch: "**/public/*.spec.ts",
      use: { ...devices["Desktop Chrome"] },
    },
    // 3. Authenticated dashboard flows, reusing the stored session.
    {
      name: "dashboard",
      testMatch: "**/dashboard/*.spec.ts",
      dependencies: ["setup"],
      use: {
        ...devices["Desktop Chrome"],
        storageState: path.resolve(__dirname, ".auth/user.json"),
      },
    },
  ],
});
