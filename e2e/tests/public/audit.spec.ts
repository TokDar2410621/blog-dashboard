import { test, expect } from "@playwright/test";

// Full public lead-magnet flow: run an audit, then unlock the full report by
// capturing an email. Uses a +alias so the J+0 email lands in Darius' inbox.
test("public audit runs and email capture unlocks the full report", async ({ page }) => {
  test.setTimeout(120_000);
  await page.goto("/audit");

  await page.getByPlaceholder("tondomaine.com").fill("example.com");
  await page.getByRole("button", { name: /Lancer l'audit/ }).click();

  // Partial results render (score + recommendations).
  await expect(page.getByText(/Score SEO global/i)).toBeVisible({ timeout: 60_000 });

  // Email gate -> unlock.
  await page.getByPlaceholder("toi@tonentreprise.com").fill("tokamdarius+e2eaudit@gmail.com");
  await page.getByRole("checkbox").first().check();
  await page.getByRole("button", { name: "Accéder au rapport complet" }).click();

  // Unlocked confirmation.
  await expect(
    page.getByText(/Rapport (complet )?d.bloqu|Cr.er mon compte/i).first()
  ).toBeVisible({ timeout: 60_000 });
});
