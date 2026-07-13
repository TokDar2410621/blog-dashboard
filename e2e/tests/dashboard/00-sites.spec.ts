import { test, expect } from "../fixtures";
import { writeSiteId } from "../lib/state";

const SITE_NAME = "E2E Test Site";

// Ensures the test account has a hosted site to drive the rest of the suite,
// and exercises the create-site + open-site flow end to end. Idempotent: if the
// site already exists it just opens it.
test("create (or reuse) a hosted site and open it", async ({ page }) => {
  await page.goto("/sites");
  await expect(page.getByRole("button", { name: "Ajouter un site" })).toBeVisible();

  const alreadyThere = await page.getByText(SITE_NAME, { exact: true }).count();
  if (alreadyThere === 0) {
    await page.getByRole("button", { name: "Ajouter un site" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.locator("#name").fill(SITE_NAME);
    await dialog.getByRole("button", { name: "Ajouter le site" }).click();
    // Dialog closes and the card shows up.
    await expect(page.getByText(SITE_NAME, { exact: true })).toBeVisible({ timeout: 20_000 });
  }

  // Open the site -> /dashboard/<id>
  await page.getByText("Ouvrir", { exact: true }).first().click();
  await page.waitForURL(/\/dashboard\/\d+/, { timeout: 30_000 });

  const m = page.url().match(/\/dashboard\/(\d+)/);
  expect(m, "dashboard URL should contain a numeric site id").not.toBeNull();
  writeSiteId(m![1]);

  await expect(
    page.getByRole("heading", { name: /Tableau de bord/ })
  ).toBeVisible({ timeout: 20_000 });
});
