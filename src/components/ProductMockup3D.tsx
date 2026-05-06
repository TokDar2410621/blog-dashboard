/**
 * ProductMockup3D - perspective-3D scene featuring blog-dashboard.
 *
 * Drop-in component, no props. Use inside any landing section:
 *   import ProductMockup3D from "@/components/ProductMockup3D";
 *   <ProductMockup3D />
 *
 * The stage uses a 2400px perspective. The main mock (article list) is
 * rotated rotateX(32deg) rotateZ(-4deg). Floating stat cards + side panel sit
 * on top in 2D, face-camera, with stacked-shadow glassmorphism.
 *
 * Below 768px we drop the 3D transform and stack the floating cards under
 * the mock for readability.
 */
import React from "react";
import {
  Sparkles,
  Search,
  Plus,
  CheckCircle2,
  Clock,
  Eye,
  ChevronDown,
  ArrowRight,
  Globe,
} from "lucide-react";

const EMERALD = "#10b981";
const EMERALD_DARK = "#059669";

// ---------------------------------------------------------------------------
// Sparkline (12 data points recommended)
// ---------------------------------------------------------------------------

function Sparkline({
  data,
  color = EMERALD,
}: {
  data: number[];
  color?: string;
}) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = 30 - ((v - min) / range) * 28;
      return `${x},${y}`;
    })
    .join(" L ");
  const linePath = `M ${points}`;
  const areaPath = `${linePath} L 100,30 L 0,30 Z`;
  const id = `pm3d-grad-${color.replace("#", "")}`;
  return (
    <svg
      viewBox="0 0 100 30"
      style={{ width: "100%", height: 32, display: "block" }}
      preserveAspectRatio="none"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${id})`} />
      <path
        d={linePath}
        stroke={color}
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Stat card (face camera, no rotation)
// ---------------------------------------------------------------------------

const CARD_SHADOW = `
  0 1px 2px rgba(15, 23, 42, 0.04),
  0 8px 24px rgba(15, 23, 42, 0.10),
  0 24px 48px rgba(15, 23, 42, 0.14)
`;

function StatCard({
  label,
  value,
  delta,
  positive = true,
  data,
  style,
  className,
}: {
  label: string;
  value: string;
  delta: string;
  positive?: boolean;
  data: number[];
  style?: React.CSSProperties;
  className?: string;
}) {
  const trendColor = positive ? EMERALD : "#ef4444";
  return (
    <div
      className={`pm3d-floating ${className ?? ""}`}
      style={{
        position: "absolute",
        width: 220,
        background: "white",
        borderRadius: 16,
        padding: 16,
        boxShadow: CARD_SHADOW,
        ...style,
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.1em",
          color: "#64748b",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 30,
          fontWeight: 700,
          color: "#0f172a",
          lineHeight: 1,
          letterSpacing: "-0.02em",
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: trendColor,
          marginTop: 6,
        }}
      >
        {delta}{" "}
        <span style={{ color: "#94a3b8", fontWeight: 400 }}>
          vs. période préc.
        </span>
      </div>
      <div style={{ marginTop: 8 }}>
        <Sparkline data={data} color={trendColor} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Side panel: AI generator preview (face camera)
// ---------------------------------------------------------------------------

function SidePanel({ style }: { style?: React.CSSProperties }) {
  return (
    <div
      className="pm3d-floating"
      style={{
        position: "absolute",
        width: 380,
        background: "white",
        borderRadius: 16,
        padding: 20,
        boxShadow: CARD_SHADOW,
        ...style,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 14,
        }}
      >
        <div
          style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: `linear-gradient(135deg, ${EMERALD} 0%, ${EMERALD_DARK} 100%)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
          }}
        >
          <Sparkles size={14} strokeWidth={2.5} />
        </div>
        <div
          style={{
            fontWeight: 700,
            fontSize: 14,
            color: "#0f172a",
          }}
        >
          Générer un article
        </div>
        <div style={{ flex: 1 }} />
        <div
          style={{
            fontSize: 10,
            fontWeight: 600,
            color: EMERALD_DARK,
            background: "rgba(16,185,129,0.10)",
            padding: "2px 8px",
            borderRadius: 999,
          }}
        >
          IA
        </div>
      </div>

      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "#475569",
          marginBottom: 6,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Sujet
      </div>
      <div
        style={{
          border: "1px solid #e2e8f0",
          borderRadius: 10,
          padding: "10px 12px",
          fontSize: 13,
          color: "#0f172a",
          marginBottom: 14,
          background: "#f8fafc",
        }}
      >
        Comment choisir un CRM pour PME au Québec
        <span
          style={{
            display: "inline-block",
            width: 1,
            height: 14,
            background: EMERALD,
            marginLeft: 2,
            verticalAlign: "middle",
            animation: "pm3d-blink 1s steps(2) infinite",
          }}
        />
      </div>

      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "#475569",
          marginBottom: 6,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Langue
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 14 }}>
        <Pill active label="FR-CA" />
        <Pill label="EN" />
        <Pill label="ES" />
      </div>

      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "#475569",
          marginBottom: 6,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        Longueur
      </div>
      <div style={{ display: "flex", gap: 6, marginBottom: 18 }}>
        <Pill label="Court" />
        <Pill active label="Moyen" />
        <Pill label="Long" />
      </div>

      <button
        type="button"
        style={{
          width: "100%",
          background: `linear-gradient(135deg, ${EMERALD} 0%, ${EMERALD_DARK} 100%)`,
          color: "white",
          border: "none",
          borderRadius: 10,
          padding: "11px 14px",
          fontWeight: 600,
          fontSize: 14,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 6,
          cursor: "default",
          boxShadow: "0 4px 12px rgba(16,185,129,0.30)",
        }}
      >
        Générer l'article <ArrowRight size={14} strokeWidth={2.5} />
      </button>

      <div
        style={{
          marginTop: 10,
          fontSize: 11,
          color: "#94a3b8",
          textAlign: "center",
        }}
      >
        Brief, recherche, rédaction, audit SEO en 90 sec.
      </div>
    </div>
  );
}

function Pill({ label, active }: { label: string; active?: boolean }) {
  return (
    <div
      style={{
        padding: "5px 12px",
        borderRadius: 999,
        fontSize: 12,
        fontWeight: 600,
        border: active ? `1.5px solid ${EMERALD}` : "1px solid #e2e8f0",
        background: active ? "rgba(16,185,129,0.08)" : "white",
        color: active ? EMERALD_DARK : "#475569",
      }}
    >
      {label}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main mock: blog-dashboard PostList view
// ---------------------------------------------------------------------------

type Article = {
  title: string;
  status: "Publié" | "Brouillon" | "Programmé";
  lang: "FR" | "EN" | "ES";
  score: number;
  date: string;
  views: number | null;
};

const ARTICLES: Article[] = [
  {
    title: "Comment choisir un CRM pour PME au Québec",
    status: "Publié",
    lang: "FR",
    score: 92,
    date: "il y a 2 j",
    views: 1247,
  },
  {
    title: "Top 10 outils SaaS québécois en 2026",
    status: "Publié",
    lang: "FR",
    score: 87,
    date: "il y a 5 j",
    views: 894,
  },
  {
    title: "Guide complet : SEO local à Montréal",
    status: "Brouillon",
    lang: "FR",
    score: 78,
    date: "Aujourd'hui",
    views: null,
  },
  {
    title: "Choosing the right CRM for Quebec SMBs",
    status: "Publié",
    lang: "EN",
    score: 84,
    date: "il y a 1 sem.",
    views: 312,
  },
  {
    title: "Stratégie de contenu B2B en français",
    status: "Programmé",
    lang: "FR",
    score: 91,
    date: "Demain 09 h",
    views: null,
  },
  {
    title: "Automatisation marketing pour TPE",
    status: "Publié",
    lang: "FR",
    score: 88,
    date: "il y a 2 sem.",
    views: 564,
  },
];

function StatusBadge({ status }: { status: Article["status"] }) {
  const map: Record<Article["status"], { bg: string; fg: string; icon: React.ReactNode }> = {
    Publié: {
      bg: "rgba(16,185,129,0.10)",
      fg: EMERALD_DARK,
      icon: <CheckCircle2 size={11} strokeWidth={2.5} />,
    },
    Brouillon: {
      bg: "rgba(148,163,184,0.15)",
      fg: "#475569",
      icon: <span style={{ width: 7, height: 7, borderRadius: 999, background: "#94a3b8" }} />,
    },
    Programmé: {
      bg: "rgba(139,92,246,0.12)",
      fg: "#7c3aed",
      icon: <Clock size={11} strokeWidth={2.5} />,
    },
  };
  const s = map[status];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "3px 9px",
        borderRadius: 999,
        background: s.bg,
        color: s.fg,
        fontWeight: 600,
        fontSize: 11,
      }}
    >
      {s.icon}
      {status}
    </span>
  );
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 85 ? EMERALD : score >= 75 ? "#f59e0b" : "#ef4444";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 100 }}>
      <div
        style={{
          flex: 1,
          height: 6,
          background: "#f1f5f9",
          borderRadius: 999,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${score}%`,
            height: "100%",
            background: color,
            borderRadius: 999,
          }}
        />
      </div>
      <span
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: "#0f172a",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {score}
      </span>
    </div>
  );
}

function MainMock() {
  return (
    <div
      style={{
        width: 980,
        background: "white",
        borderRadius: 16,
        boxShadow: "0 30px 80px rgba(15, 23, 42, 0.45)",
        overflow: "hidden",
        fontFamily:
          'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
        color: "#0f172a",
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
          <span style={{ width: 11, height: 11, borderRadius: 999, background: "#fb7185" }} />
          <span style={{ width: 11, height: 11, borderRadius: 999, background: "#fbbf24" }} />
          <span style={{ width: 11, height: 11, borderRadius: 999, background: "#34d399" }} />
        </div>
        <div
          style={{
            flex: 1,
            background: "white",
            border: "1px solid #e2e8f0",
            borderRadius: 7,
            padding: "5px 12px",
            fontSize: 12,
            color: "#64748b",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Globe size={12} strokeWidth={2} />
          app.blog-dashboard.ca/dashboard/12/posts
        </div>
      </div>

      {/* Toolbar */}
      <div
        style={{
          padding: "16px 24px",
          borderBottom: "1px solid #f1f5f9",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div>
          <div style={{ fontSize: 18, fontWeight: 700 }}>Articles</div>
          <div style={{ fontSize: 12, color: "#64748b", marginTop: 2 }}>
            47 publiés · 8 brouillons · 3 programmés
          </div>
        </div>
        <div style={{ flex: 1 }} />
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            border: "1px solid #e2e8f0",
            borderRadius: 9,
            padding: "7px 11px",
            fontSize: 13,
            color: "#64748b",
            background: "#fafbfc",
            minWidth: 220,
          }}
        >
          <Search size={14} strokeWidth={2} />
          Rechercher un article...
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            border: "1px solid #e2e8f0",
            borderRadius: 9,
            padding: "7px 11px",
            fontSize: 13,
            color: "#475569",
            background: "white",
          }}
        >
          Tous statuts
          <ChevronDown size={13} strokeWidth={2} />
        </div>
        <button
          type="button"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 5,
            background: `linear-gradient(135deg, ${EMERALD} 0%, ${EMERALD_DARK} 100%)`,
            color: "white",
            border: "none",
            padding: "8px 14px",
            borderRadius: 9,
            fontSize: 13,
            fontWeight: 600,
            cursor: "default",
            boxShadow: "0 4px 12px rgba(16,185,129,0.30)",
          }}
        >
          <Plus size={14} strokeWidth={2.5} />
          Nouvel article
        </button>
      </div>

      {/* Table header */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1fr) 110px 60px 130px 100px 80px",
          padding: "10px 24px",
          background: "#fafbfc",
          borderBottom: "1px solid #f1f5f9",
          fontSize: 10,
          fontWeight: 700,
          color: "#64748b",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          gap: 16,
        }}
      >
        <div>Titre</div>
        <div>Statut</div>
        <div>Lang.</div>
        <div>Score SEO</div>
        <div>Date</div>
        <div style={{ textAlign: "right" }}>Vues</div>
      </div>

      {/* Rows */}
      <div>
        {ARTICLES.map((a, i) => (
          <div
            key={i}
            style={{
              display: "grid",
              gridTemplateColumns: "minmax(0,1fr) 110px 60px 130px 100px 80px",
              alignItems: "center",
              padding: "14px 24px",
              borderBottom: i < ARTICLES.length - 1 ? "1px solid #f1f5f9" : "none",
              fontSize: 13,
              gap: 16,
            }}
          >
            <div
              style={{
                fontWeight: 600,
                color: "#0f172a",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title={a.title}
            >
              {a.title}
            </div>
            <div>
              <StatusBadge status={a.status} />
            </div>
            <div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.05em",
                  color: "#475569",
                  background: "#f1f5f9",
                  padding: "3px 7px",
                  borderRadius: 6,
                }}
              >
                {a.lang}
              </span>
            </div>
            <div>
              <ScoreBar score={a.score} />
            </div>
            <div style={{ color: "#64748b", fontSize: 12 }}>{a.date}</div>
            <div
              style={{
                textAlign: "right",
                color: "#475569",
                fontSize: 12,
                fontVariantNumeric: "tabular-nums",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                justifyContent: "flex-end",
              }}
            >
              {a.views !== null ? (
                <>
                  <Eye size={11} strokeWidth={2} />
                  {a.views.toLocaleString("fr-CA")}
                </>
              ) : (
                <span style={{ color: "#cbd5e1" }}>-</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main exported component
// ---------------------------------------------------------------------------

export default function ProductMockup3D() {
  return (
    <div className="pm3d-root">
      <style>{`
        @keyframes pm3d-blink { 50% { opacity: 0; } }
        .pm3d-stage {
          perspective: 2400px;
          perspective-origin: 50% 0%;
          position: relative;
          width: 100%;
          padding-top: 40px;
        }
        .pm3d-inner {
          position: relative;
          width: 980px;
          height: 580px;
          margin: 0 auto;
        }
        .pm3d-mock-wrap {
          transform: rotateX(32deg) rotateZ(-4deg);
          transform-style: preserve-3d;
          transform-origin: 50% 0%;
          transition: transform 0.4s ease-out;
        }
        @media (max-width: 1080px) {
          .pm3d-inner { transform: scale(0.85); transform-origin: 50% 0%; }
        }
        @media (max-width: 900px) {
          .pm3d-inner { transform: scale(0.7); }
        }
        @media (max-width: 768px) {
          .pm3d-stage { perspective: none; padding-top: 0; }
          .pm3d-inner {
            width: 100%;
            height: auto;
            transform: none;
          }
          .pm3d-mock-wrap {
            transform: none;
          }
          .pm3d-mock-wrap > div {
            width: 100% !important;
            min-width: 0;
          }
          .pm3d-floating {
            position: relative !important;
            top: auto !important;
            left: auto !important;
            right: auto !important;
            width: 100% !important;
            margin-top: 16px;
          }
        }
      `}</style>

      <div className="pm3d-stage">
        <div className="pm3d-inner">
          <div className="pm3d-mock-wrap">
            <MainMock />
          </div>

          {/* Stat card 1 - top right */}
          <StatCard
            label="ARTICLES PUBLIÉS"
            value="47"
            delta="+12"
            positive
            data={[8, 11, 14, 12, 18, 22, 25, 30, 35, 39, 43, 47]}
            style={{ top: 20, left: "55%" }}
          />

          {/* Stat card 2 - middle left */}
          <StatCard
            label="SCORE SEO MOYEN"
            value="89"
            delta="+4 pts"
            positive
            data={[78, 80, 82, 81, 83, 84, 85, 86, 86, 88, 88, 89]}
            style={{ top: 280, left: 30 }}
          />

          {/* Stat card 3 - bottom centered, overhang */}
          <StatCard
            label="POSITION GOOGLE MOY."
            value="8.2"
            delta="-2.1 places"
            positive
            data={[14, 13, 12.5, 12, 11, 10.5, 10, 9.5, 9, 8.7, 8.4, 8.2].map(
              (v) => 16 - v,
            )}
            style={{ top: 470, left: 280 }}
          />

          {/* Side panel - bottom right, overhang */}
          <SidePanel style={{ top: 230, right: -30 }} />
        </div>
      </div>
    </div>
  );
}
