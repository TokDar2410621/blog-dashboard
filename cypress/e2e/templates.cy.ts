describe("Templates", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
  });

  it("should show template selector with 3 tabs", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains(/nouvel article|new post/i).click();

    cy.get('[role="dialog"]').should("be.visible");
    cy.contains("Markdown").should("be.visible");
    cy.contains(/visuel|visual/i).should("be.visible");
    cy.contains("IA").should("be.visible");
  });

  it("should show markdown templates", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains(/nouvel article|new post/i).click();

    // Markdown tab is default
    cy.get('[role="dialog"]').within(() => {
      cy.contains(/actualite|news/i).should("be.visible");
      cy.contains(/tutoriel|tutorial/i).should("be.visible");
      cy.contains(/comparaison|comparison/i).should("be.visible");
    });
  });

  it("should navigate to editor with markdown template", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains(/nouvel article|new post/i).click();

    cy.get('[role="dialog"]').within(() => {
      cy.contains(/tutoriel|tutorial/i).click();
    });

    cy.url().should("include", "tpl_type=markdown");
    cy.url().should("include", "tpl_id=tutorial");
  });

  it("should show visual templates with previews", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains(/nouvel article|new post/i).click();

    cy.get('[role="dialog"]').within(() => {
      cy.contains(/visuel|visual/i).click();
      cy.contains("Hero").should("be.visible");
      cy.contains("Minimal").should("be.visible");
      // ASCII previews should be visible
      cy.get("pre").should("have.length.at.least", 1);
    });
  });

  it("should navigate to AI generator with AI template", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains(/nouvel article|new post/i).click();

    cy.get('[role="dialog"]').within(() => {
      cy.contains("IA").click();
      cy.contains(/resume rapide|quick summary/i).click();
    });

    cy.url().should("include", "/generer");
    cy.url().should("include", "tpl_id=quick-news");
  });
});
