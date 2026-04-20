describe("SEO Analysis", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
    cy.intercept("GET", "**/api/categories/", {
      body: [{ slug: "tech", name: "Tech" }],
    });
  });

  it("should show SEO tab in post editor", () => {
    cy.visit("/dashboard/1/articles/nouveau");
    cy.contains("SEO").should("be.visible");
  });

  it("should display SEO score when clicking SEO tab", () => {
    cy.visit("/dashboard/1/articles/nouveau");

    // Type some content first
    cy.get('input[placeholder]').first().type("Mon article de test sur React");

    // Click SEO tab
    cy.contains("SEO").click();

    // Should show score
    cy.contains(/score seo|seo score/i).should("be.visible");
  });

  it("should show SEO checks list", () => {
    cy.visit("/dashboard/1/articles/nouveau");
    cy.get('input[placeholder]').first().type("Un titre de test");
    cy.contains("SEO").click();

    // Should show individual checks
    cy.contains(/longueur du titre|title length/i).should("be.visible");
    cy.contains("Meta description").should("be.visible");
  });

  it("should show AI suggestions button", () => {
    cy.visit("/dashboard/1/articles/nouveau");
    cy.get('input[placeholder]').first().type("Un titre");
    cy.contains("SEO").click();

    cy.contains(/suggestions ia|ai suggestions/i).should("be.visible");
    cy.contains(/obtenir des suggestions|get suggestions/i).should("be.visible");
  });

  it("should fetch AI suggestions", () => {
    cy.intercept("POST", "**/api/seo-suggest/", {
      statusCode: 200,
      body: {
        meta_descriptions: ["A great article about React"],
        title_suggestions: ["10 React Tips You Need"],
        keywords: ["react", "javascript", "frontend"],
      },
    }).as("seoSuggest");

    cy.visit("/dashboard/1/articles/nouveau");
    cy.get('input[placeholder]').first().type("React Tips");
    cy.contains("SEO").click();
    cy.contains(/obtenir des suggestions|get suggestions/i).click();
    cy.wait("@seoSuggest");

    cy.contains("A great article about React").should("be.visible");
    cy.contains("10 React Tips You Need").should("be.visible");
    cy.contains("react").should("be.visible");
  });
});
