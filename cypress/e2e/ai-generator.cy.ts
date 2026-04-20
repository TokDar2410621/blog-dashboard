describe("AI Generator", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
  });

  it("should display the AI generation form", () => {
    cy.visit("/dashboard/1/generer");
    cy.contains(/generer un article|generate an article/i).should("be.visible");
    cy.contains(/sujet|topic/i).should("be.visible");
  });

  it("should have all form fields", () => {
    cy.visit("/dashboard/1/generer");
    // Topic input
    cy.get("input").should("have.length.at.least", 1);
    // Selects for search method, type, length
    cy.get('[data-slot="select-trigger"]').should("have.length.at.least", 3);
    // Dry run switch
    cy.get('[role="switch"]').should("exist");
  });

  it("should pre-fill form from AI template query params", () => {
    cy.visit("/dashboard/1/generer?tpl_id=deep-tutorial");
    // Should have tutorial type selected
    cy.contains(/tutoriel|tutorial/i).should("be.visible");
  });

  it("should generate an article", () => {
    cy.intercept("POST", "**/api/generate-article/", {
      statusCode: 200,
      body: {
        output: "Article generated successfully!\n\n## Introduction\n\nGenerated content...",
        post_count: 1,
      },
    }).as("generate");

    cy.visit("/dashboard/1/generer");
    cy.get("input").first().type("React Hooks");
    cy.contains(/generer|generate/i)
      .filter("button")
      .last()
      .click();
    cy.wait("@generate");
    cy.contains("Article generated").should("be.visible");
  });

  it("should show result actions after generation", () => {
    cy.intercept("POST", "**/api/generate-article/", {
      statusCode: 200,
      body: { output: "Generated!", post_count: 1 },
    }).as("generate");

    cy.visit("/dashboard/1/generer");
    cy.get("input").first().type("Test");
    cy.contains(/generer|generate/i)
      .filter("button")
      .last()
      .click();
    cy.wait("@generate");

    cy.contains(/voir les articles|view articles/i).should("be.visible");
    cy.contains(/generer un autre|generate another/i).should("be.visible");
  });
});
