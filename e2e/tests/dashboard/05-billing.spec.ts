import { test, expect } from "../fixtures";

// Billing / Stripe. GUARDRAIL: we let the real backend create a Stripe checkout
// session (proves the flow), assert the returned URL is a Stripe URL, and abort
// the actual redirect so no payment page is ever completed.
test.describe("billing", () => {
  test("billing page shows the current agency plan", async ({ page }) => {
    await page.goto("/billing");
    await expect(page.getByRole("heading", { name: "Abonnement" })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText("Agence").first()).toBeVisible();
  });

  test("buying a credits pack creates a Stripe checkout session", async ({ page }) => {
    // Never actually land on Stripe.
    await page.route(/checkout\.stripe\.com/, (r) => r.abort());
    await page.goto("/billing");

    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/api/billing/credits/buy/") &&
          r.request().method() === "POST",
        { timeout: 30_000 }
      ),
      page.getByRole("button", { name: "Acheter" }).first().click(),
    ]);

    const body = await resp.json().catch(() => ({}));
    console.log("CREDITS_CHECKOUT status=" + resp.status() + " body=" + JSON.stringify(body));
    expect(
      resp.status(),
      `Credits checkout should return 200 with a checkout URL. Got ${resp.status()} ${JSON.stringify(body)}. ` +
        `503 here = STRIPE_PRICE_CREDITS_SMALL/MEDIUM/LARGE not set in Railway (subscriptions work; only credit packs are unconfigured).`
    ).toBe(200);
    expect(body.url, "checkout url should be a Stripe URL").toContain("stripe.com");
  });

  // Hits the subscription checkout endpoint with the app's own auth token (kept
  // in the browser). In LIVE mode this only CREATES a Stripe session - no charge
  // happens until a card is entered - so it is safe to verify the revenue path.
  test("subscription checkout creates a Stripe session", async ({ page }) => {
    await page.goto("/billing");
    const res = await page.evaluate(async () => {
      const token = sessionStorage.getItem("blog_dashboard_token");
      const r = await fetch("/api/billing/checkout/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: "Bearer " + token } : {}),
        },
        credentials: "include",
        body: JSON.stringify({ plan: "pro" }),
      });
      return { status: r.status, body: await r.text() };
    });
    console.log("SUB_CHECKOUT status=" + res.status + " body=" + res.body.slice(0, 160));
    expect(
      res.status,
      `subscription checkout should succeed; got ${res.status} ${res.body.slice(0, 160)}`
    ).toBeLessThan(300);
    expect(res.body).toContain("stripe.com");
  });
});
