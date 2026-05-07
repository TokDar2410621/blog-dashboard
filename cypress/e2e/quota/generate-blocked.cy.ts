/// <reference types="cypress" />

/**
 * Generate-flow gating:
 *   - Button is pre-disabled when used >= limit AND credits === 0
 *   - Submitting from a stale state that hits 402 surfaces an inline error
 *     card with 3 CTAs (no toast, since toasts disappear)
 */
describe("AIGenerator - quota-blocked generation", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
    cy.mockCredits("empty");
  });

  it("disables the Generate button when quota is exhausted with no credits", () => {
    cy.mockBilling("free_exhausted");
    cy.visit("/dashboard/1/generer");
    cy.wait("@billingMe_free_exhausted");
    // The button should now read 'Quota épuisé · Achète des crédits' and be
    // disabled - validates the pre-flight gate works as the user would see it
    cy.get('[data-testid="generate-article"]', { timeout: 10000 })
      .should("be.disabled")
      .and("contain.text", "Quota épuisé");
  });

  it("keeps the Generate button enabled when credits cover the overflow", () => {
    cy.mockBilling("pro_exhausted_with_credits");
    cy.visit("/dashboard/1/generer");
    cy.wait("@billingMe_pro_exhausted_with_credits");
    // Generate button is back to its normal label
    cy.get('[data-testid="generate-article"]')
      .should("not.be.disabled")
      .and("be.visible");
  });

  it("renders the inline error card when generation returns 402 quota_exceeded", () => {
    // Stale UI: app loads thinking quota is fine, but the next request fails.
    cy.mockBilling("pro_healthy");
    cy.mockGenerateQuotaExceeded();
    cy.visit("/dashboard/1/generer");
    // Wait for the form to render before typing
    cy.get('input[placeholder*="tendance"]', { timeout: 10000 })
      .first()
      .clear()
      .type("Mon article test");
    cy.get('[data-testid="generate-article"]').click();
    cy.wait("@generateBlocked");

    // Inline card visible (NOT a toast)
    cy.contains("Génération bloquée").should("be.visible");
    cy.contains(/Quota mensuel atteint \(1\/1\)/).should("be.visible");
    // Three CTAs in the inline card
    cy.contains(/\+10 crédits.*25\$/).should("be.visible");
    cy.contains(/\+50 crédits.*99\$/).should("be.visible");
    cy.contains("Voir les plans").should("be.visible");
  });

  it("inline error CTA triggers a credits checkout request", () => {
    cy.mockBilling("pro_healthy");
    cy.mockGenerateQuotaExceeded();
    cy.intercept("POST", "**/api/billing/credits/buy/", {
      statusCode: 200,
      body: { url: "https://checkout.stripe.com/c/pay/cs_test_buy_small" },
    }).as("buyCreditsSmall");

    cy.visit("/dashboard/1/generer");
    cy.get('input[placeholder*="tendance"]', { timeout: 10000 })
      .first()
      .clear()
      .type("Mon article");
    cy.get('[data-testid="generate-article"]').click();
    cy.wait("@generateBlocked");

    cy.contains("button", /\+10 crédits.*25\$/).click();
    cy.wait("@buyCreditsSmall").its("request.body").should("deep.include", {
      pack: "small",
    });
    // We don't follow the redirect to checkout.stripe.com (Cypress can't
    // assert across domains anyway). The intercept above proves the right
    // payload was sent, which is what matters for the unit-of-behavior here.
  });
});
