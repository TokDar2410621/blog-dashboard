import { test, expect } from "@playwright/test";

// The "forgot password" flow must fire a reset request without error.
test("password reset request fires", async ({ page }) => {
  await page.goto("/login");
  await page.locator("#email").fill(process.env.E2E_EMAIL || "tokamdarius+e2e@gmail.com");
  await page.getByRole("button", { name: "Continuer", exact: true }).click();
  await page.locator("#password").waitFor({ state: "visible" });

  const [resp] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().includes("/auth/password/reset/request") &&
        r.request().method() === "POST",
      { timeout: 20_000 }
    ),
    page.getByRole("button", { name: /Mot de passe oubli/ }).click(),
  ]);

  expect(resp.status(), "reset request should not error").toBeLessThan(400);
});
