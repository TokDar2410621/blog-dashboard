// Base test (no sessionStorage token injection) so that after logout the app
// genuinely has no session and the guard can bounce us to /login.
import { test, expect } from "@playwright/test";
import { readSiteId } from "../lib/state";

// Logout must clear the session and bounce protected routes back to /login.
test("logout returns to the login page and protects the dashboard", async ({ page }) => {
  const siteId = readSiteId();
  await page.goto(`/dashboard/${siteId}`);
  await expect(page.getByRole("heading", { name: /Tableau de bord/ })).toBeVisible({
    timeout: 20_000,
  });

  await page.getByRole("button", { name: /D.connexion/ }).click();
  await page.waitForURL(/\/login/, { timeout: 20_000 });

  // Session gone: hitting a protected route redirects back to login.
  await page.goto(`/dashboard/${siteId}`);
  await page.waitForURL(/\/login/, { timeout: 20_000 });
});
