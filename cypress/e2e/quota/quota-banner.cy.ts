/// <reference types="cypress" />

/**
 * QuotaBanner states:
 *   - hidden when usage < warnAt (default 70%)
 *   - amber soft warning between warnAt and 100%
 *   - red hard block at 100% with no credits
 *   - amber 'using credits' notice at 100% with credits available
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
    cy.wait("@billingMe_pro_healthy");
    // No 'Quota mensuel atteint' text, no 'Plus que' nudge
    cy.contains(/Quota mensuel atteint|Plus que \d+ articles/).should("not.exist");
  });

  it("shows the amber soft warning when nearing limit (solo 7/8)", () => {
    cy.mockBilling("solo_warning");
    cy.visit("/dashboard/1/generer");
    cy.wait("@billingMe_solo_warning");
    cy.contains("Plus que").should("be.visible");
    cy.contains("1").should("be.visible"); // 8 - 7 = 1 article remaining
    cy.contains("plan solo").should("be.visible");
  });

  it("shows the red hard block when exhausted with no credits (free 1/1)", () => {
    cy.mockBilling("free_exhausted");
    cy.visit("/dashboard/1/generer");
    cy.wait("@billingMe_free_exhausted");
    cy.contains("Quota mensuel atteint").should("be.visible");
    cy.contains("1/1 articles").should("be.visible");
    cy.contains(/\+10 crédits.*25\$/).should("be.visible");
    cy.contains("Voir les plans").should("be.visible");
  });

  it("shows the amber 'using credits' notice when quota done but credits remain", () => {
    cy.mockBilling("pro_exhausted_with_credits");
    cy.visit("/dashboard/1/generer");
    cy.wait("@billingMe_pro_exhausted_with_credits");
    cy.contains("Quota mensuel atteint").should("be.visible");
    cy.contains("Tu utilises maintenant tes crédits").should("be.visible");
    cy.contains("12 disponibles").should("be.visible");
    // Hard block CTAs should NOT be there - this is the soft 'fyi' state
    cy.contains(/\+10 crédits/).should("not.exist");
  });
});
