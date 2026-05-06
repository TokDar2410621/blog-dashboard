/**
 * WorkflowIA3D - animated 4-step flow scene shown on the Landing.
 * Step 1: a sujet/topic input being typed
 * Step 2: AI streaming an article
 * Step 3: SEO audit score climbing 0->92
 * Step 4: published checkmark with URL
 *
 * Cards are arranged horizontally with arrows between. The whole row tilts
 * very slightly back. Animation triggers when the section enters the viewport
 * and loops every 8 seconds.
 */
import { useEffect, useRef, useState } from "react";
import { ArrowRight, Sparkles, FileSearch, CheckCircle2 } from "lucide-react";

const EMERALD = "#10b981";
const EMERALD_DARK = "#059669";

const TOPIC = "Comment choisir un CRM pour PME au Québec";

const ARTICLE_LINES = [
  "# Comment choisir un CRM pour PME...",
  "",
  "Pour les dirigeants de PME québécoises,",
  "le bon CRM transforme la productivité",
  "commerciale. Voici les 7 critères clés...",
  "",
  "## 1. Bilingue dès la racine",
  "Tes équipes alternent FR et EN au",
  "quotidien. Un CRM qui force l'anglais",
  "ralentit l'adoption.",
];

function useTypewriter(text: string, speed: number, start: boolean) {
  const [out, setOut] = useState("");
  useEffect(() => {
    if (!start) {
      setOut("");
      return;
    }
    let i = 0;
    let cancelled = false;
    const tick = () => {
      if (cancelled) return;
      setOut(text.slice(0, i));
      i++;
      if (i <= text.length) window.setTimeout(tick, speed);
    };
    tick();
    return () => {
      cancelled = true;
    };
  }, [text, speed, start]);
  return out;
}

function useAnimatedNumber(target: number, duration: number, start: boolean) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!start) {
      setVal(0);
      return;
    }
    let cancelled = false;
    const t0 = performance.now();
    const tick = (now: number) => {
      if (cancelled) return;
      const t = Math.min(1, (now - t0) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setVal(Math.round(eased * target));
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
    return () => {
      cancelled = true;
    };
  }, [target, duration, start]);
  return val;
}

export default function WorkflowIA3D() {
  const ref = useRef<HTMLDivElement | null>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    let started = false;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !started) {
          started = true;
          setStep(1);
          obs.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Step progression: 1 -> 2 (after typing topic) -> 3 -> 4 -> loop
  useEffect(() => {
    if (step === 0) return;
    const timings: Record<number, number> = { 1: 2400, 2: 3200, 3: 2400, 4: 4000 };
    const t = window.setTimeout(() => {
      setStep((s) => (s >= 4 ? 1 : s + 1));
    }, timings[step] ?? 2500);
    return () => window.clearTimeout(t);
  }, [step]);

  const topic = useTypewriter(TOPIC, 35, step >= 1);
  const articleText = useTypewriter(
    ARTICLE_LINES.join("\n"),
    8,
    step >= 2,
  );
  const score = useAnimatedNumber(92, 1600, step >= 3);

  return (
    <div ref={ref} className="wia3d-stage">
      <style>{`
        .wia3d-stage {
          perspective: 2400px;
          perspective-origin: 50% 0%;
          padding: 30px 0;
          position: relative;
        }
        .wia3d-row {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 14px;
          max-width: 1100px;
          margin: 0 auto;
          transform: rotateX(8deg);
          transform-style: preserve-3d;
          transform-origin: 50% 0%;
        }
        .wia3d-card {
          background: white;
          border-radius: 16px;
          padding: 16px;
          box-shadow:
            0 1px 2px rgba(15,23,42,0.04),
            0 12px 32px rgba(15,23,42,0.10),
            0 28px 60px rgba(15,23,42,0.12);
          color: #0f172a;
          font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
          min-height: 240px;
          position: relative;
        }
        .wia3d-step {
          position: absolute;
          top: -10px;
          left: 16px;
          background: ${EMERALD};
          color: white;
          font-size: 10px;
          font-weight: 700;
          padding: 3px 8px;
          border-radius: 999px;
          letter-spacing: 0.06em;
        }
        .wia3d-arrow {
          position: absolute;
          top: 50%;
          right: -22px;
          transform: translateY(-50%);
          width: 28px;
          height: 28px;
          border-radius: 999px;
          background: ${EMERALD};
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 5;
          box-shadow: 0 4px 14px rgba(16,185,129,0.40);
        }
        .wia3d-cursor {
          display: inline-block;
          width: 1.5px;
          height: 13px;
          background: ${EMERALD};
          vertical-align: -2px;
          margin-left: 1px;
          animation: wia3d-blink 1s steps(2) infinite;
        }
        @keyframes wia3d-blink { 50% { opacity: 0; } }
        @media (max-width: 900px) {
          .wia3d-row { grid-template-columns: repeat(2, minmax(0,1fr)); }
          .wia3d-arrow { display: none; }
        }
        @media (max-width: 768px) {
          .wia3d-stage { perspective: none; }
          .wia3d-row { transform: none; grid-template-columns: 1fr; gap: 24px; }
        }
      `}</style>

      <div className="wia3d-row">
        {/* Step 1 - Topic input */}
        <div className="wia3d-card">
          <span className="wia3d-step">01 · Sujet</span>
          <div className="flex items-center gap-2 mb-3 mt-2">
            <Sparkles size={14} className="text-emerald-500" strokeWidth={2.5} />
            <div style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
              Tu donnes l'idée
            </div>
          </div>
          <div
            style={{
              border: "1px solid #e2e8f0",
              borderRadius: 10,
              padding: "10px 12px",
              fontSize: 13,
              color: "#0f172a",
              minHeight: 86,
              background: "#f8fafc",
            }}
          >
            {topic}
            {step === 1 && topic !== TOPIC && <span className="wia3d-cursor" />}
          </div>
          <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                background: "rgba(16,185,129,0.10)",
                color: EMERALD_DARK,
                padding: "3px 7px",
                borderRadius: 999,
              }}
            >
              FR-CA
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                background: "#f1f5f9",
                color: "#475569",
                padding: "3px 7px",
                borderRadius: 999,
              }}
            >
              Long
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                background: "#f1f5f9",
                color: "#475569",
                padding: "3px 7px",
                borderRadius: 999,
              }}
            >
              Guide
            </span>
          </div>
          <div className="wia3d-arrow">
            <ArrowRight size={14} strokeWidth={2.5} />
          </div>
        </div>

        {/* Step 2 - AI writes */}
        <div className="wia3d-card">
          <span className="wia3d-step">02 · IA rédige</span>
          <div className="flex items-center gap-2 mb-3 mt-2">
            <div
              style={{
                width: 22,
                height: 22,
                borderRadius: 6,
                background: `linear-gradient(135deg, ${EMERALD}, ${EMERALD_DARK})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "white",
              }}
            >
              <Sparkles size={11} strokeWidth={2.5} />
            </div>
            <div style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
              Brief + recherche + rédaction
            </div>
          </div>
          <pre
            style={{
              margin: 0,
              fontFamily: "ui-monospace, SFMono-Regular, monospace",
              fontSize: 11,
              lineHeight: 1.55,
              color: "#0f172a",
              whiteSpace: "pre-wrap",
              minHeight: 120,
              maxHeight: 120,
              overflow: "hidden",
            }}
          >
            {articleText}
            {step === 2 && articleText !== ARTICLE_LINES.join("\n") && (
              <span className="wia3d-cursor" />
            )}
          </pre>
          <div className="wia3d-arrow">
            <ArrowRight size={14} strokeWidth={2.5} />
          </div>
        </div>

        {/* Step 3 - SEO audit */}
        <div className="wia3d-card">
          <span className="wia3d-step">03 · Audit SEO</span>
          <div className="flex items-center gap-2 mb-3 mt-2">
            <FileSearch size={14} className="text-emerald-500" strokeWidth={2.5} />
            <div style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
              Score auto + corrections
            </div>
          </div>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              padding: "16px 0 8px",
            }}
          >
            <div style={{ position: "relative", width: 120, height: 120 }}>
              <svg viewBox="0 0 120 120" width="120" height="120">
                <circle
                  cx="60"
                  cy="60"
                  r="50"
                  fill="none"
                  stroke="#f1f5f9"
                  strokeWidth="10"
                />
                <circle
                  cx="60"
                  cy="60"
                  r="50"
                  fill="none"
                  stroke={EMERALD}
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={`${(2 * Math.PI * 50 * score) / 100} ${2 * Math.PI * 50}`}
                  transform="rotate(-90 60 60)"
                  style={{ transition: "stroke-dasharray 0.1s" }}
                />
              </svg>
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                <span style={{ fontSize: 28, fontWeight: 800, color: "#0f172a", letterSpacing: "-0.02em" }}>
                  {score}
                </span>
                <span style={{ fontSize: 10, color: "#64748b", fontWeight: 600, letterSpacing: "0.04em" }}>
                  / 100
                </span>
              </div>
            </div>
          </div>
          <div className="wia3d-arrow">
            <ArrowRight size={14} strokeWidth={2.5} />
          </div>
        </div>

        {/* Step 4 - Published */}
        <div className="wia3d-card">
          <span className="wia3d-step">04 · Publié</span>
          <div className="flex items-center gap-2 mb-3 mt-2">
            <CheckCircle2 size={14} className="text-emerald-500" strokeWidth={2.5} />
            <div style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>
              Sur ton domaine, indexable
            </div>
          </div>

          <div
            style={{
              border: `1px solid ${step >= 4 ? "rgba(16,185,129,0.30)" : "#e2e8f0"}`,
              borderRadius: 10,
              padding: "10px 12px",
              background: step >= 4 ? "rgba(16,185,129,0.06)" : "white",
              transition: "all 0.4s",
              opacity: step >= 4 ? 1 : 0.6,
            }}
          >
            <div
              style={{
                fontFamily: "ui-monospace, SFMono-Regular, monospace",
                fontSize: 11,
                color: "#475569",
                marginBottom: 8,
                wordBreak: "break-all",
              }}
            >
              <span style={{ color: "#94a3b8" }}>https://</span>
              <span style={{ color: "#0f172a", fontWeight: 600 }}>monsite.com</span>
              <span>/blog/guide-crm-pme-quebec</span>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                fontSize: 11,
                fontWeight: 600,
                color: step >= 4 ? EMERALD_DARK : "#94a3b8",
                transition: "color 0.4s",
              }}
            >
              {step >= 4 ? (
                <>
                  <CheckCircle2 size={11} strokeWidth={2.5} />
                  <span>Indexé · sitemap mis à jour</span>
                </>
              ) : (
                <span>En attente...</span>
              )}
            </div>
          </div>

          <div
            style={{
              marginTop: 12,
              display: "flex",
              gap: 8,
              alignItems: "center",
              fontSize: 11,
              color: "#64748b",
            }}
          >
            <div
              style={{
                flex: 1,
                background: "#f8fafc",
                border: "1px solid #e2e8f0",
                borderRadius: 8,
                padding: "6px 8px",
                display: "flex",
                justifyContent: "space-between",
              }}
            >
              <span>Position Google</span>
              <span style={{ color: EMERALD_DARK, fontWeight: 600 }}>↗ #4</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
