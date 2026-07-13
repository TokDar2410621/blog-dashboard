import { test, expect } from "../fixtures";
import { readSiteId } from "../lib/state";

// Add a tracked keyword and confirm it lands in the list.
test("track a keyword on the positions page", async ({ page }) => {
  const siteId = readSiteId();
  await page.goto(`/dashboard/${siteId}/positions`);
  await expect(
    page.getByRole("heading", { name: /Suivi des positions/ })
  ).toBeVisible({ timeout: 25_000 });

  const kw = `e2e mot cle ${Date.now()}`;
  await page.getByPlaceholder(/automatisation pme|mot-cl/i).first().fill(kw);
  await page.getByRole("button", { name: "Ajouter", exact: true }).click();

  await expect(page.getByText(kw)).toBeVisible({ timeout: 25_000 });
});
