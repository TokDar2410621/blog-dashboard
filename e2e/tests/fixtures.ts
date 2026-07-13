import { test as base, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

const tokenFile = path.resolve(__dirname, "../.auth/token.txt");

// Re-inject the sessionStorage access token before app JS runs. storageState
// carries the httpOnly refresh cookie; this adds the in-memory access token so
// the dashboard is authenticated on first paint without waiting on a refresh.
export const test = base.extend({
  context: async ({ context }, use) => {
    try {
      const token = fs.readFileSync(tokenFile, "utf-8").trim();
      if (token) {
        await context.addInitScript((t) => {
          window.sessionStorage.setItem("blog_dashboard_token", t as string);
        }, token);
      }
    } catch {
      // no token file yet; cookie-based refresh will still apply
    }
    await use(context);
  },
});

export { expect };
