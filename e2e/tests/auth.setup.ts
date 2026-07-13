import { test as setup, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

const AUTH_DIR = path.resolve(__dirname, "../.auth");
const authFile = path.join(AUTH_DIR, "user.json");
const tokenFile = path.join(AUTH_DIR, "token.txt");

// Log in through the real UI (email-first state machine) and persist both the
// cookie storage state and the sessionStorage access token (Playwright's
// storageState does NOT capture sessionStorage, so we save it separately and
// re-inject it via the shared fixture).
setup("authenticate", async ({ page }) => {
  const email = process.env.E2E_EMAIL;
  const password = process.env.E2E_PASSWORD;
  if (!email || !password) throw new Error("E2E_EMAIL / E2E_PASSWORD missing in .env");

  await page.goto("/login");

  // Step 1: email
  await page.locator("#email").fill(email);
  await page.getByRole("button", { name: "Continuer", exact: true }).click();

  // Step 2: password (check-email routed us to the login step)
  await page.locator("#password").waitFor({ state: "visible" });
  await page.locator("#password").fill(password);
  await page.getByRole("button", { name: "Se connecter" }).click();

  // Lands on the site selector once authenticated.
  await page.waitForURL("**/sites", { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Ajouter un site" })).toBeVisible();

  const token = await page.evaluate(() =>
    window.sessionStorage.getItem("blog_dashboard_token")
  );

  fs.mkdirSync(AUTH_DIR, { recursive: true });
  fs.writeFileSync(tokenFile, token || "");
  await page.context().storageState({ path: authFile });
});
