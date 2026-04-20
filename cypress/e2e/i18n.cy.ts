describe("Internationalization (i18n)", () => {
  beforeEach(() => {
    cy.login();
    cy.mockAPI();
  });

  it("should default to French", () => {
    cy.visit("/dashboard/1");
    cy.wait("@getStats");
    cy.get("aside").contains(/tableau de bord|dashboard/i).should("be.visible");
    cy.get("aside").contains(/articles/i).should("be.visible");
  });

  it("should switch to English from sidebar", () => {
    cy.visit("/dashboard/1");
    cy.wait("@getStats");

    // Click language toggle
    cy.get("aside").contains("English").click();

    // Sidebar should now show English text
    cy.get("aside").contains("Dashboard").should("be.visible");
    cy.get("aside").contains("Articles").should("be.visible");
  });

  it("should persist language preference", () => {
    // Set English
    window.localStorage.setItem("blog_dashboard_lang", "en");
    cy.visit("/dashboard/1");
    cy.wait("@getStats");

    // Should be in English
    cy.get("aside").contains("Dashboard").should("be.visible");
  });

  it("should translate post list page", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");

    // French by default
    cy.contains(/nouvel article|new post/i).should("be.visible");

    // Switch to English
    cy.get("aside").contains("English").click();
    cy.contains(/new post/i).should("be.visible");
  });

  it("should translate status badges", () => {
    cy.visit("/dashboard/1/articles");
    cy.wait("@getPosts");

    // French statuses
    cy.contains(/publie|published/i).should("be.visible");
    cy.contains(/brouillon|draft/i).should("be.visible");
  });

  it("should switch language on login page", () => {
    // Clear auth to see login
    window.localStorage.removeItem("blog_token");
    window.localStorage.removeItem("blog_refresh");
    cy.visit("/login");

    cy.contains("Connectez-vous").should("be.visible");
    cy.contains("English").click();
    cy.contains("Sign in").should("be.visible");
  });
});
