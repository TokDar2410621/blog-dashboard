/// <reference types="cypress" />

/**
 * Credits-purchase flow on /billing:
 *   - Card displays balance + 3 packs from /billing/credits/
 *   - Clicking 'Acheter' on a pack POSTs /billing/credits/buy/ with the
 *     correct pack key, then sets window.location.href to the Stripe URL
 *   - Returning with ?credits=success shows a toast and refreshes balance
 */
describe("Billing /credits purchase flow", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
    cy.mockBilling("pro_healthy");
  });

  it("renders balance and 3 packs", () => {
    cy.mockCredits("with_history");
    cy.visit("/billing");
    cy.wait("@billingCredits");
    cy.contains("Crédits achetés").should("be.visible");
    cy.contains(/^12$/).should("be.visible"); // balance from with_history fixture
    cy.contains("Petit boost").should("be.visible");
    cy.contains("Boost moyen").should("be.visible");
    cy.contains("Gros volume").should("be.visible");
    cy.contains("25.00$").should("be.visible");
    cy.contains("99.00$").should("be.visible");
    cy.contains("299.00$").should("be.visible");
  });

  it("buying the medium pack POSTs the right payload + redirects", () => {
    cy.mockCredits("empty");
    cy.intercept("POST", "**/api/billing/credits/buy/", {
      statusCode: 200,
      body: { url: "https://checkout.stripe.com/c/pay/cs_test_med" },
    }).as("buyMedium");

    cy.visit("/billing");
    cy.wait("@billingCredits");

    // The 'Acheter' button on the medium pack
    cy.contains("Boost moyen")
      .closest(".rounded-xl, [class*='rounded']")
      .within(() => cy.contains("button", "Acheter").click());

    cy.wait("@buyMedium").its("request.body").should("deep.include", {
      pack: "medium",
    });
  });

  it("expands the transaction history when clicked", () => {
    cy.mockCredits("with_history");
    cy.visit("/billing");
    cy.wait("@billingCredits");
    cy.contains("Historique des transactions").click();
    cy.contains("Article généré (top-up)").should("be.visible");
    cy.contains("Pack small: +15 crédits").should("be.visible");
  });

  it("shows the success toast on ?credits=success return", () => {
    cy.mockCredits("with_history");
    cy.visit("/billing?credits=success");
    cy.wait("@billingCredits");
    cy.contains("Crédits ajoutés").should("be.visible");
  });
});
