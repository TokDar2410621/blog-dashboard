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
      `Stripe credits checkout should return 200 with a checkout URL. Got ${resp.status()} ${JSON.stringify(body)} (503 = STRIPE_SECRET_KEY not set in prod).`
    ).toBe(200);
    expect(body.url, "checkout url should be a Stripe URL").toContain("stripe.com");
  });

  test("subscription checkout creates a Stripe session", async ({ page }) => {
    await page.route(/checkout\.stripe\.com/, (r) => r.abort());
    await page.goto("/billing");

    // Any plan action button that is not the current-plan (disabled) one.
    const subscribeBtn = page
      .getByRole("button", { name: /Souscrire|Passer à/ })
      .first();
    const count = await page.getByRole("button", { name: /Souscrire|Passer à/ }).count();
    test.skip(count === 0, "no subscribe button available for the current plan");

    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/api/billing/checkout/") &&
          r.request().method() === "POST",
        { timeout: 30_000 }
      ),
      subscribeBtn.click(),
    ]);

    const body = await resp.json().catch(() => ({}));
    console.log("SUB_CHECKOUT status=" + resp.status() + " body=" + JSON.stringify(body));
    expect(
      resp.status(),
      `Stripe subscription checkout should return 200. Got ${resp.status()} ${JSON.stringify(body)}.`
    ).toBe(200);
    expect(body.url).toContain("stripe.com");
  });
});
