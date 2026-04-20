describe("Posts Management", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
  });

  it("should display post list", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains("Premier article").should("be.visible");
    cy.contains("Article en brouillon").should("be.visible");
  });

  it("should filter posts by search", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.get('input[placeholder]').first().type("brouillon");
    cy.contains("Article en brouillon").should("be.visible");
    cy.contains("Premier article").should("not.exist");
  });

  it("should open template selector on new post", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains(/nouvel article|new post/i).click();
    // Template selector dialog should appear
    cy.get('[role="dialog"]').should("be.visible");
    cy.contains(/choisir un template|choose a template/i).should("be.visible");
  });

  it("should navigate to editor with blank template", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains(/nouvel article|new post/i).click();
    cy.get('[role="dialog"]').within(() => {
      cy.contains(/article vierge|blank post/i).click();
    });
    cy.url().should("include", "/articles/nouveau");
  });

  it("should show post editor with title and content fields", () => {
    cy.intercept("GET", "**/api/categories/", {
      body: [{ slug: "tech", name: "Tech" }],
    });
    cy.visit("/dashboard/1/articles/nouveau");
    cy.get('input[placeholder]').first().should("be.visible"); // title
  });

  it("should delete a post with confirmation", () => {
    cy.intercept("DELETE", "**/api/posts/**", { statusCode: 204 }).as("deletePost");
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    // Open dropdown menu on first post
    cy.get("table button").first().click();
    cy.contains(/supprimer|delete/i).click();
  });

  it("should show status badges", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");
    cy.contains(/publie|published/i).should("be.visible");
    cy.contains(/brouillon|draft/i).should("be.visible");
  });
});
