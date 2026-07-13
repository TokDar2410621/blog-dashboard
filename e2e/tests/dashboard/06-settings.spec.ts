import { test, expect } from "../fixtures";
import { readSiteId } from "../lib/state";

// Every settings sub-page must render (auth intact, no crash).
const SUB = [
  "general",
  "branding",
  "auteur",
  "cta",
  "langues",
  "gsc",
  "memoire",
  "autopilote",
  "integrations",
];

test.describe("settings sub-pages", () => {
  for (const sub of SUB) {
    test(`parametres/${sub} renders`, async ({ page }) => {
      const siteId = readSiteId();
      await page.goto(`/dashboard/${siteId}/parametres/${sub}`);
      expect(page.url()).not.toContain("/login");
      await expect(
        page.getByRole("heading", { name: /Param.tres du site/ })
      ).toBeVisible({ timeout: 20_000 });
    });
  }
});
