import { test, expect } from "../fixtures";
import { readSiteId } from "../lib/state";

// One real AI generation end to end. We assert on the backend generate response
// (the reliable server signal) rather than post-generation UI behavior.
// GUARDRAIL: exactly one generation, spends one agency-plan article.
test("generate one AI article end to end", async ({ page }) => {
  test.setTimeout(220_000);
  const siteId = readSiteId();

  await page.goto(`/dashboard/${siteId}/generer`);
  await expect(page.getByTestId("generate-article")).toBeVisible({ timeout: 25_000 });

  // Topic (sujet).
  await page
    .getByPlaceholder(/tendances IA|Ex:/i)
    .first()
    .fill("Guide du SEO local pour une PME au Saguenay en 2026");

  const [resp] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().includes(`/sites/${siteId}/generate`) &&
        r.request().method() === "POST",
      { timeout: 200_000 }
    ),
    page.getByTestId("generate-article").click(),
  ]);

  const status = resp.status();
  const body = await resp.text().catch(() => "");
  console.log("GENERATE status=" + status + " body=" + body.slice(0, 200));
  expect(
    status,
    `AI generation should succeed; got ${status} ${body.slice(0, 200)}`
  ).toBeLessThan(300);
});
