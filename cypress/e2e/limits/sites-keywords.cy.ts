/// <reference types="cypress" />

/**
 * Plan limits beyond the article quota:
 *   - 2nd site creation by a free user → 402 + 'Limite de sites atteinte'
 *   - 1st keyword by a free user (limit=0) → 402 + 'Limite de mots-clés'
 *
 * These currently surface via toast (the connect/keyword flows still use
 * toast.error for backend errors). The toast must contain the BACKEND message,
 * not a generic one.
 */
describe("Plan limits - sites + keywords", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
    cy.mockBilling("free_exhausted"); // free plan, 1/1 quota, 1 site already
    cy.mockCredits("empty");
  });

  it("free user blocked from creating a 2nd site - toast surfaces backend message", () => {
    cy.mockSiteCreateQuotaExceeded();
    cy.visit("/sites");
    cy.wait("@getSites");

    cy.contains("Blog clé-en-main").click();
    cy.get('input[id="name"], input[placeholder*="ite"]').first().type("Mon 2e site");
    cy.contains("button", /Cr.*er/i).click();

    cy.wait("@siteCreateBlocked");
    // Toast should reference the backend French message
    cy.contains(/Limite de sites atteinte \(1\/1\)/).should("be.visible");
  });

  it("free user blocked when adding the first keyword (limit=0)", () => {
    cy.mockKeywordCreateQuotaExceeded();
    cy.intercept("GET", "**/api/sites/*/keywords/", {
      statusCode: 200,
      body: { results: [] },
    }).as("getKeywords");

    cy.visit("/dashboard/1/positions");
    cy.wait("@getKeywords");

    // Type and submit the keyword form
    cy.get('input[type="text"]').first().clear().type("crm pme québec");
    cy.contains("button", /Suivre|Ajouter/i).click({ force: true });

    cy.wait("@keywordCreateBlocked");
    cy.contains(/Limite de mots-clés atteinte/).should("be.visible");
  });
});
