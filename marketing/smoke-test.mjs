/**
 * Playwright smoke test for the Next.js migration. Visits each public
 * page + the login page + tries to reach /dashboard/1 (expects auth
 * redirect). Writes screenshots to ./screenshots/ + reports HTTP status
 * + console errors per page.
 *
 * Run AFTER `npm run dev` is up on localhost:3000.
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = "http://localhost:3000";

const PAGES = [
  { path: "/", name: "landing" },
  { path: "/blog", name: "blog-list" },
  { path: "/blog/comment-ranker-google-quebec-2026", name: "blog-post" },
  { path: "/docs", name: "docs-index" },
  { path: "/docs/connect/wordpress", name: "docs-wp" },
  { path: "/api-docs", name: "api-docs" },
  { path: "/audit", name: "audit" },
  { path: "/privacy", name: "privacy" },
  { path: "/terms", name: "terms" },
  { path: "/login", name: "login" },
  { path: "/sites", name: "sites-protected" },
  { path: "/dashboard/1", name: "dashboard-protected" },
];

async function main() {
  await mkdir("./screenshots", { recursive: true });
  const browser = await chromium.launch();
  // reducedMotion: 'reduce' makes the Reveal component immediately set visible=true
  // instead of waiting for IntersectionObserver to fire during the screenshot scroll.
  // Without this, Tailwind's motion-safe: prefix hides everything below the fold.
  const ctx = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    reducedMotion: "reduce",
  });

  const report = [];

  for (const p of PAGES) {
    const page = await ctx.newPage();
    const consoleErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("pageerror", (err) => consoleErrors.push(`[pageerror] ${err.message}`));

    const url = BASE + p.path;
    let status = null;
    let finalUrl = null;
    try {
      const resp = await page.goto(url, { waitUntil: "networkidle", timeout: 20000 });
      status = resp?.status() ?? null;
      finalUrl = page.url();
      await page.screenshot({
        path: `./screenshots/${p.name}.png`,
        fullPage: true,
      });
    } catch (e) {
      report.push({
        name: p.name,
        path: p.path,
        status: "ERROR",
        finalUrl: null,
        consoleErrors,
        navError: e.message,
      });
      await page.close();
      continue;
    }
    report.push({
      name: p.name,
      path: p.path,
      status,
      finalUrl,
      consoleErrors,
    });
    await page.close();
  }

  await browser.close();

  // Pretty print
  console.log("\n=== Smoke test report ===\n");
  for (const r of report) {
    const indicator = r.status === 200 ? "[OK]" : `[${r.status}]`;
    const redirect = r.finalUrl && r.finalUrl !== BASE + r.path ? ` -> ${r.finalUrl.replace(BASE, "")}` : "";
    console.log(`${indicator.padEnd(8)} ${r.path.padEnd(45)}${redirect}`);
    if (r.consoleErrors.length > 0) {
      for (const e of r.consoleErrors.slice(0, 3)) {
        console.log(`         ERR: ${e.substring(0, 200)}`);
      }
      if (r.consoleErrors.length > 3) {
        console.log(`         ... +${r.consoleErrors.length - 3} more errors`);
      }
    }
    if (r.navError) console.log(`         NAV: ${r.navError}`);
  }
  console.log(`\nScreenshots saved to ./screenshots/`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
