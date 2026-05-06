/**
 * Terminal3D - perspective-3D animated terminal showing a curl request hitting
 * the API and the JSON response streaming in.
 *
 * Used as the hero of the API docs page.
 */
import { useEffect, useRef, useState } from "react";

const EMERALD = "#10b981";

const COMMAND = `curl -H "Authorization: Bearer btb_xxx" \\
  https://api.blog-dashboard.ca/api/v1/sites/12/articles/`;

const RESPONSE = `{
  "results": [
    {
      "slug": "guide-crm-pme-quebec-2026",
      "title": "Comment choisir un CRM pour PME au Québec",
      "status": "published",
      "language": "fr",
      "published_at": "2026-05-04",
      "view_count": 1247
    },
    {
      "slug": "top-10-saas-quebec-2026",
      "title": "Top 10 outils SaaS québécois en 2026",
      "status": "published",
      "language": "fr",
      "published_at": "2026-05-01",
      "view_count": 894
    }
  ]
}`;

function useTypewriter(text: string, speed = 18, start = false, delay = 0) {
  const [out, setOut] = useState("");
  useEffect(() => {
    if (!start) {
      setOut("");
      return;
    }
    setOut("");
    let i = 0;
    let cancelled = false;
    const startTimer = window.setTimeout(() => {
      const tick = () => {
        if (cancelled) return;
        setOut(text.slice(0, i));
        i++;
        if (i <= text.length) {
          window.setTimeout(tick, speed);
        }
      };
      tick();
    }, delay);
    return () => {
      cancelled = true;
      window.clearTimeout(startTimer);
    };
  }, [text, speed, start, delay]);
  return out;
}

// Highlight JSON tokens minimally (keys + strings + numbers + booleans/null)
function highlightJson(json: string) {
  return json.split("\n").map((line, idx) => {
    // tokens: "key": "value" / "key": number
    const tokens = line.match(/("[^"]*"|\b\d+\b|\btrue\b|\bfalse\b|\bnull\b|[{}\[\],:])/g);
    if (!tokens) return <div key={idx}>{line || " "}</div>;
    let cursor = 0;
    const parts: React.ReactNode[] = [];
    tokens.forEach((tok, i) => {
      const at = line.indexOf(tok, cursor);
      if (at > cursor) parts.push(line.slice(cursor, at));
      cursor = at + tok.length;
      let color = "#cbd5e1"; // default punctuation
      if (/^"[^"]*"$/.test(tok)) {
        // Determine if this is a key (followed by ':') or a string value
        const after = line.slice(cursor).trimStart();
        if (after.startsWith(":")) color = "#7dd3fc";
        else color = "#86efac";
      } else if (/^\d+$/.test(tok)) color = "#fde68a";
      else if (/^(true|false)$/.test(tok)) color = "#f9a8d4";
      else if (tok === "null") color = "#94a3b8";
      parts.push(
        <span key={i} style={{ color }}>
          {tok}
        </span>,
      );
    });
    if (cursor < line.length) parts.push(line.slice(cursor));
    return <div key={idx}>{parts}</div>;
  });
}

export default function Terminal3D() {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.3 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const cmd = useTypewriter(COMMAND, 14, visible, 200);
  const cmdDone = cmd === COMMAND;
  const resp = useTypewriter(RESPONSE, 5, cmdDone, 400);

  return (
    <div ref={ref} className="t3d-stage">
      <style>{`
        .t3d-stage {
          perspective: 2400px;
          perspective-origin: 50% 0%;
          position: relative;
          width: 100%;
          padding: 30px 0;
        }
        .t3d-window {
          width: 760px;
          margin: 0 auto;
          transform: rotateX(20deg) rotateZ(-3deg);
          transform-style: preserve-3d;
          transform-origin: 50% 0%;
        }
        .t3d-cursor {
          display: inline-block;
          width: 7px;
          height: 14px;
          background: ${EMERALD};
          vertical-align: -2px;
          animation: t3d-blink 1s steps(2) infinite;
        }
        @keyframes t3d-blink { 50% { opacity: 0; } }
        @media (max-width: 860px) {
          .t3d-window { transform: rotateX(20deg) rotateZ(-3deg) scale(0.8); }
        }
        @media (max-width: 768px) {
          .t3d-stage { perspective: none; padding: 0; }
          .t3d-window { transform: none; width: 100%; }
        }
      `}</style>

      <div
        className="t3d-window"
        style={{
          background: "#0a0f1c",
          borderRadius: 14,
          boxShadow: `
            0 1px 2px rgba(0,0,0,0.3),
            0 16px 40px rgba(0,0,0,0.45),
            0 32px 70px rgba(16,185,129,0.10)
          `,
          overflow: "hidden",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
          color: "#cbd5e1",
        }}
      >
        {/* Title bar */}
        <div
          style={{
            background: "#11182a",
            padding: "10px 14px",
            display: "flex",
            alignItems: "center",
            gap: 10,
            borderBottom: "1px solid rgba(255,255,255,0.06)",
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
              textAlign: "center",
              fontSize: 12,
              color: "#94a3b8",
            }}
          >
            ~ / blog-dashboard / api
          </div>
          <div style={{ width: 50 }} />
        </div>

        {/* Body */}
        <div style={{ padding: "20px 22px 26px", fontSize: 13.5, lineHeight: 1.6, minHeight: 380 }}>
          {/* Prompt line */}
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <span style={{ color: EMERALD }}>$</span>
            <pre
              style={{
                margin: 0,
                fontFamily: "inherit",
                whiteSpace: "pre-wrap",
                color: "#e2e8f0",
              }}
            >
              {cmd}
              {!cmdDone && <span className="t3d-cursor" />}
            </pre>
          </div>

          {cmdDone && (
            <>
              {/* Status line */}
              <div
                style={{
                  fontSize: 11,
                  color: "#64748b",
                  marginBottom: 8,
                  display: "flex",
                  gap: 12,
                  alignItems: "center",
                }}
              >
                <span style={{ color: "#86efac", fontWeight: 600 }}>HTTP/2 200</span>
                <span>content-type: application/json</span>
                <span>x-ratelimit-remaining: 59</span>
              </div>

              {/* JSON response */}
              <pre
                style={{
                  margin: 0,
                  fontFamily: "inherit",
                  whiteSpace: "pre-wrap",
                  fontSize: 12.5,
                  lineHeight: 1.55,
                }}
              >
                {highlightJson(resp)}
                {resp !== RESPONSE && <span className="t3d-cursor" />}
              </pre>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
