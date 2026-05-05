import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Sparkles,
  Languages,
  CheckCircle2,
  ArrowRight,
  Newspaper,
  Search,
  PenLine,
  BarChart3,
  Zap,
  ChevronRight,
  TrendingUp,
  Globe,
  Eye,
  FileText,
  Layers,
  Link2,
  AlertTriangle,
  Award,
  ShieldCheck,
  Target,
} from "lucide-react";

// =========================================================================
// Reveal-on-scroll wrapper. Pure IntersectionObserver, no deps. Respects
// prefers-reduced-motion (skips the transition entirely).
// =========================================================================
function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  as?: React.ElementType;
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      setVisible(true);
      return;
    }
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" }
    );
    obs.observe(node);
    return () => obs.disconnect();
  }, []);
  return (
    <Tag
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`motion-safe:transition-all motion-safe:duration-[700ms] motion-safe:ease-out ${
        visible
          ? "opacity-100 translate-y-0"
          : "motion-safe:opacity-0 motion-safe:translate-y-6"
      } ${className}`}
    >
      {children}
    </Tag>
  );
}

export default function Landing() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 overflow-x-hidden">
      {/* Global animation keyframes used across the page. */}
      <style>{`
        @keyframes heroFadeUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes drawLine {
          from { stroke-dashoffset: 1000; }
          to { stroke-dashoffset: 0; }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        @keyframes glowPulse {
          0%, 100% { opacity: 0.4; }
          50% { opacity: 0.8; }
        }
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        @keyframes marqueeX {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        @media (prefers-reduced-motion: no-preference) {
          .hero-fade-1 { animation: heroFadeUp 0.7s ease-out 0.05s backwards; }
          .hero-fade-2 { animation: heroFadeUp 0.7s ease-out 0.20s backwards; }
          .hero-fade-3 { animation: heroFadeUp 0.7s ease-out 0.35s backwards; }
          .hero-fade-4 { animation: heroFadeUp 0.7s ease-out 0.50s backwards; }
          .hero-fade-5 { animation: heroFadeUp 0.7s ease-out 0.65s backwards; }
          .float-slow { animation: float 5s ease-in-out infinite; }
          .glow-pulse { animation: glowPulse 4s ease-in-out infinite; }
          .draw-line { animation: drawLine 2s ease-out 0.3s backwards; }
          .marquee-x { animation: marqueeX 30s linear infinite; }
        }
      `}</style>

      <BackgroundGrid />

      {/* Top nav */}
      <header className="relative z-20 border-b border-white/5 backdrop-blur-xl bg-zinc-950/70 sticky top-0">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 text-emerald-400" />
            <span className="font-semibold tracking-tight">Blog Dashboard</span>
          </div>
          <nav className="flex items-center gap-6">
            <a href="#features" className="hidden md:inline text-sm text-zinc-400 hover:text-white">Fonctionnalités</a>
            <a href="#pricing" className="hidden md:inline text-sm text-zinc-400 hover:text-white">Tarifs</a>
            <Link to="/login" className="text-sm text-zinc-400 hover:text-white">Connexion</Link>
            <Link to="/login">
              <Button size="sm" className="bg-white text-zinc-950 hover:bg-zinc-200">
                Commencer
              </Button>
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 pt-24 md:pt-32 pb-20">
        <RadialGlow />
        <div className="max-w-4xl mx-auto text-center">
          <div className="hero-fade-1 inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-8">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Bilingue FR-CA · IA Claude · Conçu au Québec
          </div>
          <h1 className="hero-fade-2 text-5xl md:text-7xl lg:text-8xl font-bold leading-[0.95] tracking-tighter">
            Le SEO en français qui comprend{" "}
            <span className="bg-gradient-to-br from-emerald-300 via-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              le Québec
            </span>
            .
          </h1>
          <p className="hero-fade-3 mt-8 text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            Un Ahrefs en anglais te coûte 200&nbsp;US$ et écrit "shopping". Nous, on
            génère, audite et optimise tes articles en lexique québécois - pour les PME
            qui veulent enfin ranker.
          </p>
          <div className="hero-fade-4 mt-12 flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/login">
              <Button size="lg" className="w-full sm:w-auto bg-white text-zinc-950 hover:bg-zinc-200 h-12 px-6 motion-safe:transition-transform motion-safe:hover:-translate-y-0.5">
                <Sparkles className="h-4 w-4 mr-2" />
                Connecter mon WordPress
              </Button>
            </Link>
            <a href="#features">
              <Button
                size="lg"
                variant="outline"
                className="w-full sm:w-auto h-12 px-6 bg-transparent border-white/15 hover:bg-white/5 text-zinc-100 motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
              >
                Voir comment ça marche
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </a>
          </div>
          <p className="hero-fade-5 mt-5 text-xs text-zinc-500">
            Aucune carte requise · Connecter prend 2 minutes · Annulable en un clic
          </p>
        </div>

        {/* Linear-style activity feed mockup */}
        <Reveal delay={150} className="mt-20 max-w-3xl mx-auto">
          <ActivityFeed />
        </Reveal>
      </section>

      {/* "Trusted by" marquee — subtle visual touch */}
      <section className="relative z-10 border-t border-white/5 py-10 overflow-hidden">
        <p className="text-center text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-600 mb-6">
          Construit avec
        </p>
        <div className="relative max-w-6xl mx-auto px-6">
          <div className="flex motion-safe:marquee-x gap-12 whitespace-nowrap">
            {[...TECH_LIST, ...TECH_LIST].map((label, i) => (
              <span
                key={i}
                className="text-zinc-500 text-sm font-mono shrink-0 hover:text-zinc-300 transition-colors"
              >
                {label}
              </span>
            ))}
          </div>
          {/* Edge fades */}
          <div className="absolute inset-y-0 left-0 w-24 bg-gradient-to-r from-zinc-950 to-transparent pointer-events-none" />
          <div className="absolute inset-y-0 right-0 w-24 bg-gradient-to-l from-zinc-950 to-transparent pointer-events-none" />
        </div>
      </section>

      {/* Three modes - sticky to brand promise */}
      <section className="relative z-10 max-w-6xl mx-auto px-6 py-24 border-t border-white/5">
        <Reveal className="text-center mb-16">
          <p className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-4">
            Connecté en 2 minutes
          </p>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight">
            Peu importe où vit ton blog.
          </h2>
        </Reveal>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Reveal delay={0}>
            <ModeCard
              icon={Globe}
              title="WordPress"
              tag="60% des PME québécoises"
              body="Connecte ton WP en 2 minutes via Application Password (natif WP 5.6+, aucun plugin). On lit, on génère, on republie."
            />
          </Reveal>
          <Reveal delay={120}>
            <ModeCard
              icon={Newspaper}
              title="Pas encore de blog"
              tag="On t'en bâtit un"
              body="Blog Next.js complet, hébergé chez nous, sur ton sous-domaine blog.tonsite.ca. SEO Québec optimisé out-of-the-box."
            />
          </Reveal>
          <Reveal delay={240}>
            <ModeCard
              icon={Zap}
              title="Site existant non-WP"
              tag="Wix, Shopify, custom"
              body="Cloudflare Worker, Vercel rewrites, Nginx - guides clé-en-main pour servir notre blog sous tonsite.ca/blog."
            />
          </Reveal>
        </div>
      </section>

      {/* Features section with live mockups */}
      <section id="features" className="relative z-10 max-w-6xl mx-auto px-6 py-24 border-t border-white/5">
        <Reveal className="text-center mb-20">
          <p className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-4">
            Le parcours SEO complet
          </p>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight">
            Du brief au ranking, en un seul outil.
          </h2>
          <p className="mt-6 text-zinc-400 max-w-2xl mx-auto">
            24 outils intégrés. Tu n&apos;as plus besoin d&apos;Ahrefs, Surfer, Frase et Originality
            séparément.
          </p>
        </Reveal>

        {/* Phase 1 - Recherche */}
        <FeatureRow
          phase="01"
          icon={Search}
          title="Recherche stratégique"
          subtitle="Avant d'écrire, on t'équipe avec ce que les top SERP ont dans la tête."
          features={[
            "Brief de contenu (intent + outline + FAQ + entités + EEAT)",
            "People Also Ask + schema FAQPage prêt à coller",
            "Questions Reddit / Quora - la vraie phrasing de tes lecteurs",
            "Google Trends FR-CA avec graphique 12 mois",
            "Top 10 SERP avec word count médian + structure",
          ]}
          mockup={<BriefMockup />}
        />

        {/* Phase 2 - Génération */}
        <FeatureRow
          phase="02"
          icon={PenLine}
          title="Génération en lexique québécois"
          subtitle="Claude écrit en suivant TON brief, avec ta voix. Pas un Ahrefs traduit."
          features={[
            "Article complet généré sur ton outline",
            "Knowledge base personnelle (ta voix, tes anecdotes)",
            "Lexique FR-CA auto (week-end → fin de semaine)",
            "Anti-cannibalisation (refuse les doublons)",
            "Schema.org Article + EEAT Person auto-injecté",
          ]}
          mockup={<LexiconMockup />}
          reverse
        />

        {/* Phase 3 - Optimisation */}
        <FeatureRow
          phase="03"
          icon={BarChart3}
          title="Suivi & optimisation continue"
          subtitle="Audit IA, alertes positions, détection de déclin. On garde ton SEO vivant."
          features={[
            "Audit IA (per-article + bulk site-wide)",
            "Suivi positions Google quotidien (graphe 90 j)",
            "Détection de déclin via GSC + alertes",
            "Topic clusters (pillars + spokes)",
            "Maillage interne (orphelins, hubs, dead-ends)",
          ]}
          mockup={<RankMockup />}
        />
      </section>

      {/* Quebec differentiator */}
      <section className="relative z-10 py-24 border-t border-white/5">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <Reveal>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-6">
                <Languages className="h-3 w-3" />
                Le différenciant Québec
              </div>
              <h2 className="text-3xl md:text-5xl font-bold tracking-tight leading-[0.95]">
                Pas un Ahrefs traduit en{" "}
                <span className="text-zinc-500 line-through">français de France</span>.
              </h2>
              <p className="mt-8 text-zinc-400 text-lg leading-relaxed">
                Surfer écrit "shopping". Frase écrit "week-end". Ahrefs écrit "parking".
                Tes lecteurs québécois sont allergiques. Nous, on connaît la différence
                entre <em className="text-emerald-300 not-italic">magasiner</em>,{" "}
                <em className="text-emerald-300 not-italic">fin de semaine</em>,{" "}
                <em className="text-emerald-300 not-italic">stationnement</em> et{" "}
                <em className="text-emerald-300 not-italic">courriel</em>.
              </p>
              <ul className="mt-8 space-y-4">
                {[
                  ["Lexique FR-CA intégré", "50+ termes France→Québec auto-détectés en live dans l'éditeur"],
                  ["Schema LocalBusiness québécois", "addressRegion=QC, areaServed=Québec, conventions OQLF"],
                  ["Géo Google Trends FR-CA", "tendances réelles du marché québécois, pas Paris"],
                  ["EEAT bilingue", "JSON-LD Person en FR-CA avec credentials adaptés"],
                ].map(([title, desc]) => (
                  <li key={title} className="flex items-start gap-3">
                    <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-semibold">{title}</div>
                      <div className="text-sm text-zinc-500">{desc}</div>
                    </div>
                  </li>
                ))}
              </ul>
            </Reveal>
            <Reveal delay={150}>
              <LexiconLiveMockup />
            </Reveal>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="relative z-10 py-24 border-t border-white/5">
        <div className="max-w-6xl mx-auto px-6">
          <Reveal className="text-center mb-16">
            <p className="text-xs font-mono uppercase tracking-wider text-zinc-500 mb-4">
              Tarifs en CAD · sans lock-in
            </p>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">
              Simple. Honnête. Pas un piège SaaS.
            </h2>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-5xl mx-auto">
            <Reveal delay={0}>
              <PriceCard
                name="Essai"
                price="0$"
                period="pour toujours"
                hint="Sans carte"
                features={[
                  "1 site",
                  "5 articles / mois",
                  "Audit IA basique",
                  "Brief de contenu",
                  "Suivi 5 mots-clés",
                ]}
                cta="Commencer"
              />
            </Reveal>
            <Reveal delay={120}>
              <PriceCard
                name="Pro"
                price="79$"
                period="/mois"
                highlight
                hint="Le plus populaire"
                features={[
                  "3 sites (WP, hébergé, externe)",
                  "Articles illimités",
                  "24 outils SEO",
                  "Suivi 50 mots-clés + GSC + alertes",
                  "Audit bulk + topic clusters",
                  "Lexique FR-CA + EEAT + LocalBusiness",
                  "Rapport hebdomadaire PDF",
                  "Support email <24h",
                ]}
                cta="Commencer Pro"
              />
            </Reveal>
            <Reveal delay={240}>
              <PriceCard
                name="Agence"
                price="199$"
                period="/mois"
                hint="Pour gérer 10 clients"
                features={[
                  "10 sites",
                  "Tout du plan Pro",
                  "Comparaison multi-domaines",
                  "Suivi 200 mots-clés",
                  "White-label optionnel",
                  "Onboarding personnalisé",
                  "Support prioritaire <4h",
                ]}
                cta="Choisir Agence"
              />
            </Reveal>
          </div>
          <p className="text-center text-sm text-zinc-500 mt-12">
            Plus de 10 sites ou intégration custom ?{" "}
            <a href="mailto:tokamdarius@gmail.com" className="text-emerald-400 hover:underline">
              On en jase
            </a>
            .
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="relative z-10 max-w-3xl mx-auto px-6 py-24 border-t border-white/5">
        <Reveal>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight text-center mb-16">
            Questions fréquentes
          </h2>
        </Reveal>
        <div className="space-y-3">
          {FAQS.map((item, i) => (
            <Reveal key={i} delay={i * 60}>
              <details
                className="group border border-white/10 rounded-xl px-5 py-4 hover:border-white/20 motion-safe:transition-all motion-safe:duration-200 [&_summary::-webkit-details-marker]:hidden"
              >
                <summary className="cursor-pointer flex items-center justify-between font-semibold gap-4">
                  <span>{item.q}</span>
                  <ChevronRight className="h-4 w-4 text-zinc-500 motion-safe:transition-transform motion-safe:duration-200 group-open:rotate-90" />
                </summary>
                <p className="mt-4 text-sm text-zinc-400 leading-relaxed">{item.a}</p>
              </details>
            </Reveal>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="relative z-10 py-24 border-t border-white/5">
        <RadialGlow />
        <Reveal className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-4xl md:text-6xl font-bold tracking-tight leading-[0.95]">
            Tes concurrents écrivent encore dans Word.
          </h2>
          <p className="mt-6 text-lg text-zinc-400">
            Toi tu auras un brief stratégique aligné sur le SERP, un article que Claude
            rédige en lexique québécois, et un audit IA qui te dit exactement quoi
            corriger. En 10 minutes par article.
          </p>
          <div className="mt-12">
            <Link to="/login">
              <Button size="lg" className="bg-white text-zinc-950 hover:bg-zinc-200 h-12 px-8 text-base motion-safe:transition-transform motion-safe:duration-200 motion-safe:hover:-translate-y-0.5 motion-safe:hover:scale-[1.02]">
                <Sparkles className="h-4 w-4 mr-2" />
                Commencer gratuitement
              </Button>
            </Link>
          </div>
        </Reveal>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/5">
        <div className="max-w-6xl mx-auto px-6 py-12 text-sm text-zinc-500">
          <div className="flex flex-col md:flex-row justify-between gap-8">
            <div className="max-w-md">
              <div className="flex items-center gap-2 mb-3 text-zinc-100">
                <Newspaper className="h-5 w-5 text-emerald-400" />
                <span className="font-semibold">Blog Dashboard</span>
              </div>
              <p>
                Le SaaS SEO bilingue FR-CA, conçu et opéré au Québec. Pour les PME
                québécoises qui veulent ranker. Aucun investisseur, aucun pivot prévu.
              </p>
            </div>
            <div className="flex flex-wrap gap-6 items-start">
              <a href="mailto:tokamdarius@gmail.com" className="hover:text-zinc-100">Contact</a>
              <Link to="/login" className="hover:text-zinc-100">Connexion</Link>
              <a href="#pricing" className="hover:text-zinc-100">Tarifs</a>
              <a
                href="https://github.com/TokDar2410621/blog-dashboard"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-zinc-100"
              >
                GitHub
              </a>
            </div>
          </div>
          <div className="mt-12 pt-6 border-t border-white/5 text-xs flex justify-between items-center">
            <span>© {new Date().getFullYear()} Blog Dashboard</span>
            <span>Fait à Saint-Hyacinthe, QC.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

// =========================================================================
// Sub-components
// =========================================================================

function BackgroundGrid() {
  return (
    <>
      {/* Grid pattern */}
      <div
        className="fixed inset-0 z-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgb(255 255 255 / 1) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 1) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
      {/* Top fade */}
      <div className="fixed inset-x-0 top-0 h-[40vh] z-0 pointer-events-none bg-gradient-to-b from-emerald-500/[0.05] via-transparent to-transparent" />
    </>
  );
}

function RadialGlow() {
  return (
    <div className="absolute inset-0 -z-10 pointer-events-none overflow-hidden">
      <div className="absolute top-0 left-1/2 -translate-x-1/2 h-[600px] w-[1000px] rounded-full bg-gradient-to-br from-emerald-500/20 via-cyan-500/10 to-transparent blur-3xl motion-safe:glow-pulse" />
    </div>
  );
}

// --- Activity feed (Linear-style) -----------------------------------------

const FEED_ITEMS: Array<{
  icon: typeof Sparkles;
  badge: string;
  badgeColor: string;
  text: string;
  highlight?: string;
  meta: string;
}> = [
  {
    icon: PenLine,
    badge: "PUBLIÉ",
    badgeColor: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
    text: "Article",
    highlight: "« Comment retenir les développeurs au Québec »",
    meta: "il y a 2 min",
  },
  {
    icon: TrendingUp,
    badge: "RANK",
    badgeColor: "text-cyan-300 bg-cyan-500/10 border-cyan-500/30",
    text: "« automatisation pme québec »",
    highlight: "#14 → #8",
    meta: "il y a 5 min",
  },
  {
    icon: Award,
    badge: "AUDIT",
    badgeColor: "text-violet-300 bg-violet-500/10 border-violet-500/30",
    text: "Score IA",
    highlight: "82/100",
    meta: "il y a 12 min",
  },
  {
    icon: Sparkles,
    badge: "BRIEF",
    badgeColor: "text-amber-300 bg-amber-500/10 border-amber-500/30",
    text: "Brief généré pour",
    highlight: "« marketing courriel pme »",
    meta: "il y a 18 min",
  },
  {
    icon: AlertTriangle,
    badge: "DÉCLIN",
    badgeColor: "text-orange-300 bg-orange-500/10 border-orange-500/30",
    text: "Impressions",
    highlight: "-42% sur 30j",
    meta: "il y a 1 h",
  },
  {
    icon: Globe,
    badge: "WP",
    badgeColor: "text-blue-300 bg-blue-500/10 border-blue-500/30",
    text: "WordPress connecté",
    highlight: "monsalon.ca",
    meta: "il y a 2 h",
  },
  {
    icon: Layers,
    badge: "CLUSTER",
    badgeColor: "text-pink-300 bg-pink-500/10 border-pink-500/30",
    text: "5 topic clusters détectés",
    meta: "il y a 3 h",
  },
  {
    icon: Target,
    badge: "MOT-CLÉ",
    badgeColor: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
    text: "+3 mots-clés ajoutés au suivi",
    meta: "il y a 5 h",
  },
  {
    icon: Link2,
    badge: "MAILLAGE",
    badgeColor: "text-indigo-300 bg-indigo-500/10 border-indigo-500/30",
    text: "2 articles orphelins détectés",
    meta: "il y a 6 h",
  },
  {
    icon: ShieldCheck,
    badge: "AI 23%",
    badgeColor: "text-emerald-300 bg-emerald-500/10 border-emerald-500/30",
    text: "Article",
    highlight: "« TPS et TVQ pour solo »",
    meta: "il y a 8 h",
  },
];

function ActivityFeed() {
  // Triple the array for seamless infinite scroll
  const tripled = [...FEED_ITEMS, ...FEED_ITEMS, ...FEED_ITEMS];
  return (
    <div className="relative">
      <div className="absolute -inset-px rounded-2xl bg-gradient-to-b from-emerald-500/30 via-cyan-500/10 to-transparent blur-xl pointer-events-none" />
      <div className="relative rounded-2xl border border-white/10 bg-zinc-900/80 backdrop-blur-xl overflow-hidden">
        {/* Window chrome */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
          </div>
          <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-500 flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Activité - tokamdarius.ca
          </div>
          <span className="text-[10px] text-zinc-600">live</span>
        </div>

        {/* Scrolling feed */}
        <div className="relative h-[280px] overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-12 bg-gradient-to-b from-zinc-900 to-transparent z-10 pointer-events-none" />
          <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-zinc-900 to-transparent z-10 pointer-events-none" />
          <div className="animate-feed-scroll">
            {tripled.map((item, i) => {
              const Icon = item.icon;
              return (
                <div
                  key={i}
                  className="flex items-start gap-3 px-5 py-3 border-b border-white/5"
                >
                  <span className="mt-0.5 shrink-0 h-7 w-7 rounded-md bg-zinc-800 border border-white/5 flex items-center justify-center">
                    <Icon className="h-3.5 w-3.5 text-zinc-300" />
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${item.badgeColor}`}
                      >
                        {item.badge}
                      </span>
                      <span className="text-sm text-zinc-300">
                        {item.text}
                        {item.highlight && (
                          <>
                            {" "}
                            <span className="font-semibold text-white">
                              {item.highlight}
                            </span>
                          </>
                        )}
                      </span>
                    </div>
                  </div>
                  <span className="text-[10px] text-zinc-500 shrink-0 mt-1 font-mono">
                    {item.meta}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Inject the keyframes */}
      <style>{`
        @keyframes feedScroll {
          0% { transform: translateY(0); }
          100% { transform: translateY(-33.333%); }
        }
        .animate-feed-scroll {
          animation: feedScroll 40s linear infinite;
        }
      `}</style>
    </div>
  );
}

// --- Mode card ------------------------------------------------------------

function ModeCard({
  icon: Icon,
  title,
  tag,
  body,
}: {
  icon: typeof Globe;
  title: string;
  tag: string;
  body: string;
}) {
  return (
    <div className="group relative rounded-2xl border border-white/10 bg-zinc-900/40 hover:bg-zinc-900/60 hover:border-emerald-400/30 backdrop-blur-sm p-6 motion-safe:transition-all motion-safe:duration-300 motion-safe:hover:-translate-y-1 motion-safe:hover:shadow-[0_8px_30px_rgba(52,211,153,0.08)]">
      <div className="absolute inset-0 -z-10 rounded-2xl bg-gradient-to-br from-emerald-500/0 to-emerald-500/0 group-hover:from-emerald-500/10 group-hover:to-transparent motion-safe:transition-colors motion-safe:duration-500" />
      <div className="flex items-start justify-between mb-4">
        <Icon className="h-6 w-6 text-emerald-400 motion-safe:transition-transform motion-safe:duration-300 motion-safe:group-hover:scale-110" />
        <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">{tag}</span>
      </div>
      <h3 className="font-semibold text-lg mb-2">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
    </div>
  );
}

// --- Feature row (alternates left/right) ---------------------------------

function FeatureRow({
  phase,
  icon: Icon,
  title,
  subtitle,
  features,
  mockup,
  reverse,
}: {
  phase: string;
  icon: typeof Search;
  title: string;
  subtitle: string;
  features: string[];
  mockup: React.ReactNode;
  reverse?: boolean;
}) {
  return (
    <div
      className={`grid grid-cols-1 lg:grid-cols-2 gap-12 items-center mb-32 last:mb-0 ${
        reverse ? "lg:[direction:rtl]" : ""
      }`}
    >
      <Reveal
        delay={0}
        className={`space-y-6 ${reverse ? "lg:[direction:ltr]" : ""}`}
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-emerald-400">PHASE {phase}</span>
          <span className="h-px flex-1 bg-gradient-to-r from-emerald-500/40 to-transparent" />
        </div>
        <div className="flex items-center gap-3">
          <span className="h-10 w-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center motion-safe:float-slow">
            <Icon className="h-5 w-5 text-emerald-400" />
          </span>
          <h3 className="text-2xl md:text-3xl font-bold">{title}</h3>
        </div>
        <p className="text-zinc-400 text-lg">{subtitle}</p>
        <ul className="space-y-2">
          {features.map((f, i) => (
            <li
              key={f}
              className="flex items-start gap-2.5 text-sm text-zinc-300 motion-safe:transition-transform motion-safe:hover:translate-x-1"
              style={{ animationDelay: `${100 + i * 60}ms` }}
            >
              <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>{f}</span>
            </li>
          ))}
        </ul>
      </Reveal>
      <Reveal delay={150} className={reverse ? "lg:[direction:ltr]" : ""}>
        {mockup}
      </Reveal>
    </div>
  );
}

// --- Mockups -------------------------------------------------------------

function MockupFrame({ children, label }: { children: React.ReactNode; label: string }) {
  return (
    <div className="relative">
      <div className="absolute -inset-px rounded-2xl bg-gradient-to-br from-emerald-500/20 via-cyan-500/10 to-transparent blur-xl pointer-events-none" />
      <div className="relative rounded-2xl border border-white/10 bg-zinc-900/80 backdrop-blur-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
          </div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">{label}</span>
          <span />
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

function BriefMockup() {
  return (
    <MockupFrame label="brief - automatisation pme québec">
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs font-mono text-zinc-500 uppercase tracking-wider">
          <Search className="h-3 w-3" />
          Search intent
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded text-[10px] font-mono uppercase bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">
            Informational
          </span>
          <span className="text-xs text-zinc-500">+ commercial mid-funnel</span>
        </div>

        <div className="border-t border-white/5 pt-3 mt-4">
          <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider mb-2">
            Outline suggéré (médiane top 10)
          </div>
          <ul className="space-y-1.5 text-sm">
            <li className="flex items-center gap-2">
              <span className="text-emerald-400 font-mono text-xs">H2</span>
              <span>Pourquoi automatiser sa PME en 2026</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-emerald-400 font-mono text-xs">H2</span>
              <span>Les 5 outils essentiels (Make, n8n, Zapier...)</span>
            </li>
            <li className="flex items-center gap-2 pl-5">
              <span className="text-cyan-400 font-mono text-xs">H3</span>
              <span className="text-zinc-400 text-xs">Comparaison prix CAD</span>
            </li>
            <li className="flex items-center gap-2">
              <span className="text-emerald-400 font-mono text-xs">H2</span>
              <span>Cas concret : restaurant à Montréal</span>
            </li>
          </ul>
        </div>

        <div className="border-t border-white/5 pt-3 mt-2 flex items-center justify-between text-xs">
          <span className="text-zinc-500">Cible : 1 850 mots</span>
          <span className="text-zinc-500">8 entités · 6 FAQ</span>
        </div>
      </div>
    </MockupFrame>
  );
}

function LexiconMockup() {
  return (
    <MockupFrame label="éditeur - lisibilité + lexique fr-ca">
      <div className="space-y-4">
        <div className="space-y-2 font-mono text-xs">
          <div className="text-zinc-500 uppercase tracking-wider mb-2 flex items-center gap-2">
            <Languages className="h-3 w-3" />
            5 termes France détectés
          </div>
          {[
            ["shopping", "magasinage"],
            ["week-end", "fin de semaine"],
            ["parking", "stationnement"],
            ["email", "courriel"],
            ["startup", "jeune pousse"],
          ].map(([from, to]) => (
            <div key={from} className="flex items-center gap-2 text-sm">
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30 font-mono w-8 text-center">
                ×1
              </span>
              <span className="line-through text-zinc-500">{from}</span>
              <ArrowRight className="h-3 w-3 text-zinc-600" />
              <span className="text-emerald-300 font-medium">{to}</span>
            </div>
          ))}
        </div>

        <div className="border-t border-white/5 pt-4">
          <div className="flex items-end justify-between">
            <div>
              <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider">
                Score Flesch
              </div>
              <div className="text-3xl font-bold text-emerald-400 mt-1">72</div>
              <div className="text-xs text-zinc-500 mt-0.5">Facile · lecteur ~12 ans</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-zinc-500">phrases : <span className="text-zinc-300">14</span></div>
              <div className="text-xs text-zinc-500">mots/phrase : <span className="text-zinc-300">15.2</span></div>
              <div className="text-xs text-zinc-500">ARI : <span className="text-zinc-300">7.8</span></div>
            </div>
          </div>
          <div className="h-1.5 w-full rounded bg-zinc-800 mt-3 overflow-hidden">
            <div className="h-full w-[72%] bg-gradient-to-r from-emerald-500 to-cyan-500" />
          </div>
        </div>
      </div>
    </MockupFrame>
  );
}

function RankMockup() {
  // Sparkline data: position values (lower = better, so "going up" visually = improving)
  const positions = [22, 19, 17, 18, 14, 12, 13, 9, 8, 8];
  const max = 25;
  const min = 0;
  const W = 360;
  const H = 100;
  const points = positions
    .map((p, i) => {
      const x = (i / (positions.length - 1)) * W;
      // Invert: lower position = higher on chart
      const y = H - ((max - p) / (max - min)) * H;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <MockupFrame label="suivi positions - automatisation pme québec">
      <div className="space-y-4">
        <div className="flex items-end justify-between">
          <div>
            <div className="text-xs font-mono text-zinc-500 uppercase tracking-wider">
              Position actuelle
            </div>
            <div className="text-4xl font-bold text-emerald-400 flex items-baseline gap-2 mt-1">
              #8
              <span className="text-xs text-emerald-400 font-mono">↑ 14 places</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs font-mono text-zinc-500">10 derniers jours</div>
            <div className="text-xs text-emerald-300 font-mono mt-1 flex items-center gap-1 justify-end">
              <TrendingUp className="h-3 w-3" />
              en hausse
            </div>
          </div>
        </div>

        {/* SVG sparkline with animated draw-on-mount */}
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-24">
            <defs>
              <linearGradient id="rankGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgb(52 211 153)" stopOpacity="0.4" />
                <stop offset="100%" stopColor="rgb(52 211 153)" stopOpacity="0" />
              </linearGradient>
            </defs>
            {/* Reference line for top 10 */}
            <line
              x1="0"
              y1={H - ((max - 10) / (max - min)) * H}
              x2={W}
              y2={H - ((max - 10) / (max - min)) * H}
              stroke="rgb(52 211 153 / 0.2)"
              strokeDasharray="4 4"
            />
            <polygon
              points={`0,${H} ${points} ${W},${H}`}
              fill="url(#rankGradient)"
              className="motion-safe:[animation:heroFadeUp_1.2s_ease-out_0.6s_backwards]"
            />
            <polyline
              points={points}
              fill="none"
              stroke="rgb(52 211 153)"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="motion-safe:draw-line"
              style={{ strokeDasharray: 1000 }}
            />
            {positions.map((p, i) => {
              const x = (i / (positions.length - 1)) * W;
              const y = H - ((max - p) / (max - min)) * H;
              return (
                <circle
                  key={i}
                  cx={x}
                  cy={y}
                  r={i === positions.length - 1 ? 4 : 2}
                  fill="rgb(52 211 153)"
                  className="motion-safe:[animation:heroFadeUp_0.4s_ease-out_backwards]"
                  style={{ animationDelay: `${1.0 + i * 0.08}s` }}
                />
              );
            })}
          </svg>
          <div className="text-[10px] text-zinc-600 font-mono flex justify-between mt-1">
            <span>↑ #1 (meilleur)</span>
            <span>seuil top 10</span>
            <span>↓ hors top 25</span>
          </div>
        </div>
      </div>
    </MockupFrame>
  );
}

function LexiconLiveMockup() {
  return (
    <div className="relative">
      <div className="absolute -inset-px rounded-2xl bg-gradient-to-br from-emerald-500/20 via-cyan-500/10 to-transparent blur-xl pointer-events-none" />
      <div className="relative rounded-2xl border border-white/10 bg-zinc-900/80 backdrop-blur-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
          </div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400">
            lexique québécois - live
          </span>
          <span />
        </div>
        <div className="p-6 space-y-3 font-mono text-sm">
          {[
            ["shopping", "magasinage", "OQLF"],
            ["week-end", "fin de semaine", "OQLF"],
            ["parking", "stationnement", "OQLF"],
            ["email", "courriel", "OQLF"],
            ["login", "identifiant", "OQLF"],
            ["startup", "jeune pousse", "OQLF"],
            ["spam", "pourriel", "OQLF"],
            ["podcast", "baladodiffusion", "OQLF"],
            ["lycéen", "cégépien", "système éducatif QC"],
            ["TVA", "TPS + TVQ", "fiscalité QC"],
          ].map(([from, to, src]) => (
            <div key={from} className="flex items-center gap-3">
              <span className="line-through text-zinc-500 w-32 truncate">{from}</span>
              <ArrowRight className="h-3 w-3 text-zinc-600 shrink-0" />
              <span className="text-emerald-300 font-medium flex-1 truncate">{to}</span>
              <span className="text-[10px] text-zinc-600 shrink-0">{src}</span>
            </div>
          ))}
          <div className="text-xs text-zinc-500 pt-3 border-t border-white/5 mt-3">
            + 40 autres termes auto-détectés en live dans l&apos;éditeur
          </div>
        </div>
      </div>
    </div>
  );
}

// --- Pricing ---------------------------------------------------------------

function PriceCard({
  name,
  price,
  period,
  hint,
  features,
  cta,
  highlight,
}: {
  name: string;
  price: string;
  period: string;
  hint: string;
  features: string[];
  cta: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={`relative rounded-2xl p-6 motion-safe:transition-all motion-safe:duration-300 motion-safe:hover:-translate-y-1 ${
        highlight
          ? "bg-gradient-to-b from-emerald-500/10 to-zinc-900/40 border-2 border-emerald-500/40 motion-safe:hover:shadow-[0_12px_40px_rgba(52,211,153,0.15)]"
          : "bg-zinc-900/40 border border-white/10 hover:border-white/20 motion-safe:hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]"
      }`}
    >
      {highlight && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-emerald-500 text-zinc-950 text-[10px] font-mono uppercase tracking-wider font-bold">
          {hint}
        </div>
      )}
      {!highlight && (
        <div className="absolute top-6 right-6 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
          {hint}
        </div>
      )}
      <h3 className="font-semibold text-lg">{name}</h3>
      <div className="mt-4">
        <span className="text-4xl font-bold">{price}</span>
        <span className="text-sm text-zinc-500"> {period}</span>
      </div>
      <ul className="mt-6 space-y-2 text-sm">
        {features.map((f) => (
          <li key={f} className="flex items-start gap-2">
            <CheckCircle2
              className={`h-4 w-4 shrink-0 mt-0.5 ${
                highlight ? "text-emerald-400" : "text-zinc-500"
              }`}
            />
            <span className={highlight ? "text-zinc-200" : "text-zinc-400"}>{f}</span>
          </li>
        ))}
      </ul>
      <Link to="/login">
        <Button
          className={`w-full mt-8 ${
            highlight
              ? "bg-emerald-500 text-zinc-950 hover:bg-emerald-400"
              : "bg-white/5 hover:bg-white/10 text-zinc-100 border border-white/10"
          }`}
        >
          {cta}
        </Button>
      </Link>
    </div>
  );
}

// --- Tech stack marquee --------------------------------------------------

const TECH_LIST = [
  "Anthropic Claude",
  "Gemini 2.5 Flash",
  "Google Search Console",
  "Serper SERP",
  "Originality.ai",
  "WordPress REST API",
  "PageSpeed Insights",
  "Pexels",
  "Vercel Edge",
  "Railway",
  "Stripe",
  "Schema.org",
];

// --- FAQ data --------------------------------------------------------------

const FAQS = [
  {
    q: "Mon site n'est pas WordPress, est-ce que ça marche ?",
    a: "Oui. Trois options : (1) on t'héberge un blog Next.js complet sur ton sous-domaine, (2) tu utilises un proxy Cloudflare/Vercel/Nginx pour servir notre blog sous /blog de ton domaine, (3) tu peux exporter chaque article en HTML/Markdown pour le coller dans Wix, Squarespace, Shopify, etc.",
  },
  {
    q: "Quelle IA est utilisée ?",
    a: "Anthropic Claude pour la génération d'articles (la meilleure IA pour le long-form en 2026), Gemini 2.5 Flash pour les audits SEO et les analyses (rapide + bon marché), Serper pour les SERP Google. Tu n'as à gérer aucune clé d'API.",
  },
  {
    q: "Combien de temps pour connecter mon WordPress ?",
    a: "2 minutes. Tu vas dans ton WP admin → Profil → Application Passwords → tu génères un token → tu colles dans notre dashboard. Aucun plugin à installer. Natif WP 5.6+.",
  },
  {
    q: "Est-ce que le contenu sera détecté comme IA par Google ?",
    a: "Non si tu nous donnes ta knowledge base personnelle (ta voix, tes anecdotes). Le brief stratégique force Claude à suivre une structure unique par article. On intègre aussi des signaux EEAT (auteur réel, credentials, dates) que Google récompense. On peut aussi scanner via Originality.ai.",
  },
  {
    q: "Combien d'articles puis-je générer par mois ?",
    a: "Plan Essai : 5/mois. Plans Pro et Agence : illimité. Le seul vrai coût pour nous c'est l'API Claude - on absorbe ça dans le prix.",
  },
  {
    q: "Et si je veux annuler ?",
    a: "Un clic dans tes paramètres. Pas de frais d'annulation. Tu gardes tes articles publiés (sur ton WP ou sur le blog hébergé que tu peux migrer).",
  },
];
