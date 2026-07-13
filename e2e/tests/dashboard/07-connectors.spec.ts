import { test, expect } from "../fixtures";

// Each CMS connector button on /sites must open its dialog.
test.describe("site connectors", () => {
  for (const cms of ["WordPress", "Shopify", "Webflow"]) {
    test(`${cms} connect dialog opens`, async ({ page }) => {
      await page.goto("/sites");
      await page.getByRole("button", { name: cms, exact: true }).click();
      await expect(page.getByRole("dialog")).toBeVisible({ timeout: 10_000 });
      await page.keyboard.press("Escape");
    });
  }
});
