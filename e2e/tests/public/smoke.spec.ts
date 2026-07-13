import { test, expect } from "@playwright/test";

// Harness sanity: does the whole Playwright -> chromium -> live prod chain work?
test.describe("public smoke", () => {
  test("homepage loads with Gridar title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/Gridar/i);
  });

  test("public audit page renders a domain input", async ({ page }) => {
    await page.goto("/audit");
    await expect(page.locator("input").first()).toBeVisible();
  });

  test("category landing renders its h1", async ({ page }) => {
    await page.goto("/logiciel-seo-quebec");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });
});
