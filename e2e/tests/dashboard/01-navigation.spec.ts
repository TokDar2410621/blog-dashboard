import { test, expect } from "../fixtures";
import { readSiteId } from "../lib/state";

// Smoke every dashboard page: it must render its own heading (not redirect to
// /login, not crash). This is the highest-value launch gate: it catches broken
// routes across the whole app in one pass.
const ROUTES: { path: string; heading: RegExp }[] = [
  { path: "", heading: /Tableau de bord/ },
  { path: "/audit-site", heading: /Audit du site/ },
  { path: "/opportunites", heading: /Opportunit/ },
  { path: "/articles", heading: /Articles/ },
  { path: "/audit-global", heading: /Audit SEO global/ },
  { path: "/positions", heading: /Suivi des positions/ },
  { path: "/decay", heading: /d.clin/i },
  { path: "/clusters", heading: /Topic clusters/ },
  { path: "/link-graph", heading: /Maillage interne|Graphe de maillage/ },
  { path: "/redirects", heading: /Redirections 301/ },
  { path: "/broken-links", heading: /liens cass/i },
  { path: "/digest", heading: /Rapport hebdomadaire/ },
  { path: "/images", heading: /Images/ },
  { path: "/serp-analyzer", heading: /Analyseur SERP/ },
  { path: "/ai-visibility", heading: /Visibilite IA|Visibilit. IA/ },
  { path: "/parametres", heading: /Param.tres/ },
];

test.describe("dashboard navigation smoke", () => {
  for (const route of ROUTES) {
    test(`renders ${route.path || "/(overview)"}`, async ({ page }) => {
      const siteId = readSiteId();
      const resp = await page.goto(`/dashboard/${siteId}${route.path}`);
      // Not bounced to the login wall.
      expect(page.url(), "should not redirect to /login").not.toContain("/login");
      // HTTP response should not be a hard error.
      if (resp) expect(resp.status(), `status for ${route.path}`).toBeLessThan(400);
      // Own heading renders (page mounted, data-independent).
      await expect(
        page.getByRole("heading", { name: route.heading }).first()
      ).toBeVisible({ timeout: 25_000 });
    });
  }

  test("generer page mounts the generate button", async ({ page }) => {
    const siteId = readSiteId();
    await page.goto(`/dashboard/${siteId}/generer`);
    expect(page.url()).not.toContain("/login");
    await expect(page.getByTestId("generate-article")).toBeVisible({ timeout: 25_000 });
  });
});
