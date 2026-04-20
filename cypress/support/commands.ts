/// <reference types="cypress" />

declare global {
  namespace Cypress {
    interface Chainable {
      login(): Chainable<void>;
      mockAPI(): Chainable<void>;
    }
  }
}

Cypress.Commands.add("login", () => {
  cy.intercept("POST", "**/api/token/", {
    statusCode: 200,
    body: { access: "fake-access-token", refresh: "fake-refresh-token" },
  }).as("login");

  window.localStorage.setItem("blog_token", "fake-access-token");
  window.localStorage.setItem("blog_refresh", "fake-refresh-token");
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

export {};
