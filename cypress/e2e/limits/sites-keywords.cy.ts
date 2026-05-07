/// <reference types="cypress" />

/**
 * Plan limits beyond the article quota:
 *   - 2nd site creation by a free user → 402 + 'Limite de sites atteinte'
 *   - 1st keyword by a free user (limit=0) → 402 + 'Limite de mots-clés'
 *
 * The connect/keyword flows still use toast.error for backend errors. The
 * toast must contain the BACKEND message, not a generic one.
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

    // Open the hosted-blog dialog
    cy.contains(/clé-en-main/i, { timeout: 10000 }).click();

    // Type a name into the dialog (placeholder 'Mon blog')
    cy.get('input#name', { timeout: 10000 }).type("Mon 2e site");

    // Submit - the button reads 'Ajouter le site'
    cy.contains("button", /^Ajouter le site/i).click();

    // Validates the user-visible contract: the backend's French error MUST
    // surface as a visible toast (not occluded by the Radix Dialog overlay).
    // Originally failed with toast occluded → fixed by closing the dialog
    // on error so the toast is rendered above the empty page.
    cy.get('[data-sonner-toast]', { timeout: 10000 })
      .should("be.visible")
      .and("contain.text", "Limite de sites atteinte");
  });

  it("free user blocked when adding the first keyword (limit=0)", () => {
    cy.mockKeywordCreateQuotaExceeded();
    cy.intercept("GET", "**/api/sites/*/keywords/", {
      statusCode: 200,
      body: { results: [] },
    }).as("getKeywords");

    cy.visit("/dashboard/1/positions");

    // Type into the keyword input (placeholder 'Ex: ...')
    cy.get('input[placeholder*="Ex:"]', { timeout: 10000 })
      .first()
      .type("crm pme québec");

    // Submit - button label is 'Ajouter'
    cy.contains("button", /^Ajouter$/i).click();

    cy.get('[data-sonner-toast]', { timeout: 10000 })
      .should("be.visible")
      .and("contain.text", "Limite de mots-clés atteinte");
  });
});
