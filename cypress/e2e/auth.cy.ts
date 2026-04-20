describe("Authentication", () => {
  beforeEach(() => {
    cy.intercept("POST", "**/api/token/", {
      statusCode: 200,
      body: { access: "fake-access-token", refresh: "fake-refresh-token" },
    }).as("login");
  });

  it("should show login page when not authenticated", () => {
    cy.visit("/");
    cy.url().should("include", "/login");
    cy.contains("Blog Dashboard").should("be.visible");
  });

  it("should login successfully with valid credentials", () => {
    cy.visit("/login");
    cy.get('input[type="text"]').type("admin");
    cy.get('input[type="password"]').type("password123");
    cy.get('button[type="submit"]').click();
    cy.wait("@login");
    cy.url().should("include", "/sites");
  });

  it("should show error on invalid credentials", () => {
    cy.intercept("POST", "**/api/token/", {
      statusCode: 401,
      body: { detail: "Invalid credentials" },
    }).as("loginFail");

    cy.visit("/login");
    cy.get('input[type="text"]').type("wrong");
    cy.get('input[type="password"]').type("wrong");
    cy.get('button[type="submit"]').click();
    cy.wait("@loginFail");
    cy.get('[data-sonner-toast]').should("exist");
  });

  it("should redirect to login when accessing protected route", () => {
    cy.visit("/sites");
    cy.url().should("include", "/login");
  });

  it("should toggle language on login page", () => {
    cy.visit("/login");
    // Default is French
    cy.contains("Connectez-vous").should("be.visible");
    // Switch to English
    cy.contains("English").click();
    cy.contains("Sign in to manage your sites").should("be.visible");
  });
});
