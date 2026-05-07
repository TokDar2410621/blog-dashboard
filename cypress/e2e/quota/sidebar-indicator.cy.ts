/// <reference types="cypress" />

/**
 * The QuotaIndicator at the bottom of DashboardSidebar shows the current
 * plan + 'used / limit' counter, a progress bar that recolors at 80% and
 * 100%, and the credit balance. Clicking navigates to /billing.
 */
describe("DashboardSidebar QuotaIndicator", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
  });

  it("shows the plan name and current usage", () => {
    cy.mockBilling("pro_healthy");
    cy.visit("/dashboard/1");
    cy.wait("@billingMe_pro_healthy");
    cy.contains(/^pro$/i).should("be.visible");
    cy.contains("20 / 60").should("be.visible");
    cy.contains(/0 crédits?/).should("be.visible");
  });

  it("shows 'X / Y' counter for free plan even at zero", () => {
    cy.mockBilling("free_fresh");
    cy.visit("/dashboard/1");
    cy.wait("@billingMe_free_fresh");
    cy.contains(/^free$/i).should("be.visible");
    cy.contains("0 / 1").should("be.visible");
  });

  it("displays credit balance when present (free + 5 credits)", () => {
    cy.mockBilling("free_with_credits");
    cy.visit("/dashboard/1");
    cy.wait("@billingMe_free_with_credits");
    cy.contains("5 crédits").should("be.visible");
  });

  it("navigates to /billing when clicked", () => {
    cy.mockBilling("pro_healthy");
    cy.visit("/dashboard/1");
    cy.wait("@billingMe_pro_healthy");
    cy.contains("Voir mon plan et mes crédits")
      .parent()
      .click({ force: true });
    cy.url().should("include", "/billing");
  });

  it("shows '1 crédit' (singular) when balance is exactly 1", () => {
    // Custom scenario inline
    cy.intercept("GET", "**/api/billing/me/", {
      statusCode: 200,
      body: {
        plan: "free",
        status: "active",
        is_paid: false,
        current_period_end: null,
        cancel_at_period_end: false,
        limits: { sites_max: 1, articles_per_month: 1, keywords_max: 0 },
        usage: { articles_this_month: 1, month_key: "2026-05" },
        credits: { balance: 1 },
      },
    }).as("billingMe_one_credit");
    cy.visit("/dashboard/1");
    cy.wait("@billingMe_one_credit");
    cy.contains(/^1 crédit$/).should("be.visible"); // singular
  });
});
