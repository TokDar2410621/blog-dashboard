/// <reference types="cypress" />

export type BillingScenario =
  | "free_fresh"
  | "free_exhausted"
  | "free_with_credits"
  | "solo_warning"
  | "pro_healthy"
  | "pro_exhausted_with_credits";

declare global {
  namespace Cypress {
    interface Chainable {
      login(): Chainable<void>;
      mockAPI(): Chainable<void>;
      mockBilling(scenario: BillingScenario): Chainable<void>;
      mockCredits(variant?: "empty" | "with_history"): Chainable<void>;
      mockGenerateQuotaExceeded(): Chainable<void>;
      mockSiteCreateQuotaExceeded(): Chainable<void>;
      mockKeywordCreateQuotaExceeded(): Chainable<void>;
    }
  }
}

Cypress.Commands.add("login", () => {
  cy.intercept("POST", "**/api/token/", {
    statusCode: 200,
    body: { access: "fake-access-token", refresh: "fake-refresh-token" },
  }).as("login");

  // Mock the user-identity endpoint AuthGuard relies on; without this the
  // guard would redirect to /login before any test page renders. We accept
  // both `/auth/me/` and `/auth/me` to be defensive against trailing-slash
  // differences.
  cy.intercept("GET", "**/api/auth/me/**", {
    statusCode: 200,
    body: {
      id: 1,
      username: "alice_demo",
      email: "alice@example.test",
      first_name: "",
      last_name: "",
    },
  }).as("authMe");

  // The app reads its token from sessionStorage under the key
  // 'blog_dashboard_token' (see src/lib/constants.ts > LS_KEY). Setting the
  // wrong key (or wrong storage) silently makes AuthGuard redirect to /login.
  // We seed sessionStorage on every page Cypress will visit (Cypress wipes
  // window state between visits, so set it via window.beforeunload prevention
  // or reseed before each visit by exposing it as a separate command).
  cy.window().then((win) => {
    win.sessionStorage.setItem("blog_dashboard_token", "fake-access-token");
    win.sessionStorage.setItem("blog_dashboard_refresh", "fake-refresh-token");
  });
});

// Seed sessionStorage tokens on EVERY page load. Cypress clears
// sessionStorage between cy.visit calls in the same test, so we hook
// 'window:before:load' to reseed before each navigation.
beforeEach(() => {
  cy.on("window:before:load", (win) => {
    win.sessionStorage.setItem("blog_dashboard_token", "fake-access-token");
    win.sessionStorage.setItem("blog_dashboard_refresh", "fake-refresh-token");
  });
});

Cypress.Commands.add("mockAPI", () => {
  cy.intercept("GET", "**/api/sites/", {
    fixture: "sites.json",
  }).as("getSites");

  cy.intercept("GET", "**/api/posts/**", {
    fixture: "posts.json",
  }).as("getPosts");

  cy.intercept("GET", "**/api/stats/", {
    fixture: "stats.json",
  }).as("getStats");

  cy.intercept("GET", "**/api/categories/", {
    body: [
      { slug: "tech", name: "Tech" },
      { slug: "news", name: "News" },
    ],
  }).as("getCategories");
});

// ---------------------------------------------------------------------------
// Quota + credits scenarios
// ---------------------------------------------------------------------------

/** Mock /billing/me/ to return one of the predefined scenarios.
 * Use to drive QuotaBanner, sidebar QuotaIndicator and pre-flight states. */
Cypress.Commands.add("mockBilling", (scenario: BillingScenario) => {
  cy.fixture("billing-scenarios.json").then((scenarios) => {
    cy.intercept("GET", "**/api/billing/me/", {
      statusCode: 200,
      body: scenarios[scenario],
    }).as(`billingMe_${scenario}`);
  });
});

/** Mock /billing/credits/ list endpoint. */
Cypress.Commands.add("mockCredits", (variant = "empty") => {
  cy.fixture("credits.json").then((data) => {
    cy.intercept("GET", "**/api/billing/credits/", {
      statusCode: 200,
      body: data[variant],
    }).as("billingCredits");
  });
});

/** Mock POST /sites/<id>/generate/ to return 402 quota_exceeded.
 * Use to assert the inline upgrade card surfaces correctly. */
Cypress.Commands.add("mockGenerateQuotaExceeded", () => {
  cy.intercept("POST", "**/api/sites/*/generate/", {
    statusCode: 402,
    body: {
      error:
        "Quota mensuel atteint (1/1) et aucun crédit disponible. Achète des crédits sur /billing ou attends le début du mois prochain.",
      quota_exceeded: true,
    },
  }).as("generateBlocked");
});

/** Mock POST /sites/ to return 402 sites limit exceeded. */
Cypress.Commands.add("mockSiteCreateQuotaExceeded", () => {
  cy.intercept("POST", "**/api/sites/", {
    statusCode: 402,
    body: {
      error:
        "Limite de sites atteinte (1/1). Mets ton plan à niveau sur /billing pour ajouter un site supplémentaire.",
      quota_exceeded: true,
      limit_type: "sites",
    },
  }).as("siteCreateBlocked");
});

/** Mock POST /sites/<id>/keywords/ to return 402 keyword limit exceeded. */
Cypress.Commands.add("mockKeywordCreateQuotaExceeded", () => {
  cy.intercept("POST", "**/api/sites/*/keywords/", {
    statusCode: 402,
    body: {
      error:
        "Limite de mots-clés atteinte (0/0). Mets ton plan à niveau sur /billing ou retire un mot-clé pour en suivre un autre.",
      quota_exceeded: true,
      limit_type: "keywords",
    },
  }).as("keywordCreateBlocked");
});

export {};
