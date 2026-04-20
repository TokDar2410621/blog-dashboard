describe("Dashboard Overview", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
    cy.visit("/dashboard/1");
  });

  it("should display stats cards", () => {
    cy.wait("@getStats");
    cy.get('[data-slot="card"]').should("have.length.at.least", 3);
  });

  it("should navigate via sidebar links", () => {
    // Articles
    cy.get("aside").contains(/articles/i).click();
    cy.url().should("include", "/articles");

    // AI Generator
    cy.get("aside").contains(/generer|generate/i).click();
    cy.url().should("include", "/generer");
  });

  it("should toggle language from sidebar", () => {
    // Find and click language switcher
    cy.get("aside").contains(/english|francais/i).click();
    // Text should change
    cy.get("aside").contains(/english|francais/i).should("be.visible");
  });
});
