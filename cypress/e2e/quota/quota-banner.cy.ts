/// <reference types="cypress" />

/**
 * QuotaBanner states. We mock /billing/me/ then assert on visible content.
 * (cy.wait on alias is brittle when multiple queries race; UI-driven asserts
 * are the resilient pattern.)
 *
 * The banner sits inside AIGenerator at /dashboard/:siteId/generer
 */
describe("QuotaBanner", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
    cy.mockCredits("empty");
  });

  it("hides when usage is below the warning threshold (pro 20/60)", () => {
    cy.mockBilling("pro_healthy");
    cy.visit("/dashboard/1/generer");
    // Page mounted → form visible. Banner is hidden.
    cy.get('[data-testid="generate-article"]', { timeout: 10000 }).should("be.visible");
    cy.contains(/Quota mensuel atteint|Plus que \d+ articles?/).should("not.exist");
  });

  it("shows the amber soft warning when nearing limit (solo 7/8)", () => {
    cy.mockBilling("solo_warning");
    cy.visit("/dashboard/1/generer");
    cy.contains("Plus que", { timeout: 10000 }).should("be.visible");
    cy.contains(/plan solo/).should("be.visible");
  });

  it("shows the red hard block when exhausted with no credits (free 1/1)", () => {
    cy.mockBilling("free_exhausted");
    cy.visit("/dashboard/1/generer");
    cy.contains("Quota mensuel atteint", { timeout: 10000 }).should("be.visible");
    cy.contains("1/1 articles").should("be.visible");
    cy.contains(/\+10 crédits/).should("be.visible");
    cy.contains("Voir les plans").should("be.visible");
  });

  it("shows the amber 'using credits' notice when quota done but credits remain", () => {
    cy.mockBilling("pro_exhausted_with_credits");
    cy.visit("/dashboard/1/generer");
    cy.contains("Quota mensuel atteint", { timeout: 10000 }).should("be.visible");
    cy.contains("Tu utilises maintenant tes crédits").should("be.visible");
    cy.contains("12 disponibles").should("be.visible");
  });
});
