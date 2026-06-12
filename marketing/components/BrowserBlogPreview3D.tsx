/**
 * BrowserBlogPreview3D - perspective-3D mockup of a blog article rendered on
 * the user's own domain, with the user's branding applied. Used in the
 * onboarding-external flow to preview "voilà ton blog" before they paste any
 * code.
 *
 * Props:
 *   domain         - the user's site domain (e.g., "monsite.com")
 *   brandColor     - hex color (defaults to emerald)
 *   brandFg        - foreground color on brand background (defaults to white)
 *   logoUrl        - optional logo URL
 *   siteName       - displayed in the header (defaults to domain)
 *   articleTitle   - displayed as h1 in the article body
 *   articleExcerpt - displayed as lead paragraph
 */
import React from "react";

const EMERALD = "#10b981";

const SHADOW = `
  0 1px 2px rgba(15, 23, 42, 0.04),
  0 12px 32px rgba(15, 23, 42, 0.12),
  0 32px 60px rgba(15, 23, 42, 0.18)
`;

type Props = {
  domain?: string;
  brandColor?: string;
  brandFg?: string;
  logoUrl?: string;
  siteName?: string;
  articleTitle?: string;
  articleExcerpt?: string;
};

export default function BrowserBlogPreview3D({
  domain = "monsite.com",
  brandColor = EMERALD,
  brandFg = "#ffffff",
  logoUrl,
  siteName,
  articleTitle = "Comment choisir un CRM pour PME au Québec en 2026",
  articleExcerpt = "Guide complet pour les dirigeants de PME québécoises : critères, prix, intégrations, support en français-québécois. On compare les 7 solutions les plus pertinentes pour le marché local.",
}: Props) {
  const displayName = siteName || domain.replace(/^https?:\/\//, "").replace(/^www\./, "");
  const slug = "guide-crm-pme-quebec-2026";

  return (
    <div className="bbp3d-root">
      <style>{`
        .bbp3d-stage {
          perspective: 2400px;
          perspective-origin: 50% 0%;
          position: relative;
          width: 100%;
          padding: 30px 0 60px;
        }
        .bbp3d-window {
          width: 880px;
          margin: 0 auto;
          transform: rotateX(22deg) rotateZ(-3deg);
          transform-style: preserve-3d;
          transform-origin: 50% 0%;
        }
        @media (max-width: 980px) {
          .bbp3d-window { transform: rotateX(22deg) rotateZ(-3deg) scale(0.85); }
        }
        @media (max-width: 768px) {
          .bbp3d-stage { perspective: none; padding: 0; }
          .bbp3d-window { transform: none; width: 100%; }
        }
      `}</style>
      <div className="bbp3d-stage">
        <div
          className="bbp3d-window"
          style={{
            background: "white",
            borderRadius: 16,
            boxShadow: SHADOW,
            overflow: "hidden",
            color: "#0f172a",
            fontFamily:
              'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          }}
        >
          {/* Browser chrome */}
          <div
            style={{
              background: "#f8fafc",
              borderBottom: "1px solid #e2e8f0",
              padding: "10px 14px",
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <div style={{ display: "flex", gap: 6 }}>
              <span
                style={{ width: 11, height: 11, borderRadius: 999, background: "#fb7185" }}
              />
              <span
                style={{ width: 11, height: 11, borderRadius: 999, background: "#fbbf24" }}
              />
              <span
                style={{ width: 11, height: 11, borderRadius: 999, background: "#34d399" }}
              />
            </div>
            <div
              style={{
                flex: 1,
                background: "white",
                border: "1px solid #e2e8f0",
                borderRadius: 7,
                padding: "5px 12px",
                fontSize: 12,
                color: "#475569",
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontFamily: "ui-monospace, SFMono-Regular, monospace",
              }}
            >
              <span style={{ color: "#94a3b8" }}>https://</span>
              <span style={{ color: "#0f172a", fontWeight: 600 }}>{domain}</span>
              <span style={{ color: "#475569" }}>/blog/{slug}</span>
            </div>
          </div>

          {/* Site header (with brand color accent) */}
          <header
            style={{
              borderBottom: "1px solid #f1f5f9",
              padding: "16px 32px",
              display: "flex",
              alignItems: "center",
              gap: 14,
            }}
          >
            {logoUrl ? (
              <img
                src={logoUrl}
                alt=""
                style={{ height: 28, width: "auto", maxWidth: 120, objectFit: "contain" }}
              />
            ) : (
              <div
                style={{
                  height: 28,
                  width: 28,
                  borderRadius: 8,
                  background: brandColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: brandFg,
                  fontWeight: 700,
                  fontSize: 14,
                }}
              >
                {displayName.charAt(0).toUpperCase()}
              </div>
            )}
            <div style={{ fontWeight: 700, fontSize: 14, color: "#0f172a" }}>
              {displayName}
            </div>
            <div style={{ flex: 1 }} />
            <nav style={{ display: "flex", gap: 24, fontSize: 13, color: "#475569" }}>
              <span>Accueil</span>
              <span>Produits</span>
              <span style={{ color: brandColor, fontWeight: 600 }}>Blog</span>
              <span>Contact</span>
            </nav>
          </header>

          {/* Article body */}
          <article style={{ padding: "32px 56px 36px", maxWidth: 700, margin: "0 auto" }}>
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                color: brandColor,
                marginBottom: 12,
              }}
            >
              SEO · CRM · PME Québec
            </div>
            <h1
              style={{
                fontSize: 30,
                fontWeight: 800,
                letterSpacing: "-0.02em",
                lineHeight: 1.15,
                color: "#0f172a",
                marginBottom: 14,
              }}
            >
              {articleTitle}
            </h1>
            <div
              style={{
                fontSize: 13,
                color: "#64748b",
                marginBottom: 22,
                display: "flex",
                gap: 12,
                alignItems: "center",
              }}
            >
              <span>Par l'équipe {displayName}</span>
              <span>·</span>
              <span>6 mai 2026</span>
              <span>·</span>
              <span>8 min de lecture</span>
            </div>
            <p
              style={{
                fontSize: 16,
                lineHeight: 1.6,
                color: "#334155",
                marginBottom: 18,
              }}
            >
              {articleExcerpt}
            </p>
            <h2
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: "#0f172a",
                marginTop: 22,
                marginBottom: 10,
              }}
            >
              Pourquoi un CRM en 2026 ?
            </h2>
            <p
              style={{
                fontSize: 15,
                lineHeight: 1.65,
                color: "#475569",
                marginBottom: 12,
              }}
            >
              Pour les PME québécoises, les outils traditionnels (Excel, courriels) atteignent
              vite leurs limites. Un CRM bien choisi t'évite les pertes de leads, automatise les
              relances, et te donne des...
            </p>

            {/* CTA card with brand color */}
            <div
              style={{
                marginTop: 22,
                padding: "16px 18px",
                borderRadius: 12,
                background: `linear-gradient(135deg, ${brandColor}10, ${brandColor}05)`,
                border: `1px solid ${brandColor}40`,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  letterSpacing: "0.05em",
                  color: brandColor,
                  textTransform: "uppercase",
                  marginBottom: 4,
                }}
              >
                À retenir
              </div>
              <div style={{ fontSize: 14, color: "#0f172a", lineHeight: 1.5 }}>
                Le bon CRM pour ta PME doit être bilingue, intégré à tes outils existants, et
                avoir un support en français-québécois.
              </div>
            </div>
          </article>
        </div>
      </div>
    </div>
  );
}
