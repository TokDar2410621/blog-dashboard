describe("Site Selector", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
    cy.visit("/sites");
  });

  it("should display list of sites", () => {
    cy.wait("@getSites");
    cy.contains("Mon Blog Tech").should("be.visible");
    cy.contains("Blog Voyage").should("be.visible");
  });

  it("should navigate to dashboard on site selection", () => {
    cy.wait("@getSites");
    cy.contains("Mon Blog Tech").click();
    cy.url().should("include", "/dashboard/1");
  });

  it("should show site domains", () => {
    cy.wait("@getSites");
    cy.contains("tech.example.com").should("be.visible");
  });
});
