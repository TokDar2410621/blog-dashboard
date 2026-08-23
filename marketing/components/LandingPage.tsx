"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Hero10 } from "@/components/ui/hero-10";
import WorkflowIA3D from "@/components/WorkflowIA3D";
import { MarketingHeader } from "@/components/MarketingHeader";
import {
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
  Layers,
  Link2,
  ShieldCheck,
} from "lucide-react";
import { ContainerScroll } from "@/components/ui/container-scroll-animation";
import { CinematicFooter } from "@/components/ui/motion-footer";
import { DashboardDemo } from "@/components/DashboardDemo";

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

export default function LandingPage() {
  // Auth-aware CTAs: if the visitor already has a valid session, every
  // "Connexion" / "Commencer" link points to /sites (site selector) instead
  // of /login. isLoading guards the SSR/hydration mismatch flash.
  const { isAuthenticated } = useAuth();
  const authedHref = isAuthenticated ? "/sites" : "/login";
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
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        @media (prefers-reduced-motion: no-preference) {
          .hero-fade-1 { animation: heroFadeUp 0.7s ease-out 0.05s backwards; }
          .hero-fade-2 { animation: heroFadeUp 0.7s ease-out 0.20s backwards; }
          .hero-fade-3 { animation: heroFadeUp 0.7s ease-out 0.35s backwards; }
          .hero-fade-4 { animation: heroFadeUp 0.7s ease-out 0.50s backwards; }
          .hero-fade-5 { animation: heroFadeUp 0.7s ease-out 0.65s backwards; }
          .float-slow { animation: float 5s ease-in-out infinite; }
          .draw-line { animation: drawLine 2s ease-out 0.3s backwards; }
        }
      `}</style>

      <BackgroundGrid />

      {/* Top nav */}
      <MarketingHeader />

      {/* Hero. Le champ d'audit reste DANS le hero via `action` : un hero qui
          promet vaut moins qu'un hero ou l'outil tourne deja. Les trois
          captures de /public/hero sont de vraies captures du produit, la
          premiere sur le site public, les deux autres sur le tableau de bord
          de demonstration (donnees de demo, jamais celles d'un client). */}
      <Hero10
        title="Le SEO fait pour toi."
        titleLine2Prefix="Pour les PME"
        titleHighlight="du Québec"
        description="Entre ton URL. En 60 secondes, on te sort exactement ce qui t’empêche de ranker sur Google au Québec : tags, schéma, vitesse, mots-clés, contenu manquant."
        animation="subtle"
        action={<HeroAuditInput authedHref={authedHref} />}
        primaryCTA={{
          ctaEnabled: true,
          text: isAuthenticated ? "Tableau de bord" : "Créer un compte gratuit",
          link: authedHref,
          variant: "default",
          size: "lg",
        }}
        secondaryCTA={{
          ctaEnabled: true,
          text: "Voir comment ça marche",
          link: "#features",
          variant: "ghost",
          size: "lg",
        }}
        socialProof="Sans carte · Audit complet en 60 secondes · 100% confidentiel"
        images={[
          "/hero/1-input.png",
          "/hero/2-produit.png",
          "/hero/3-positions.png",
        ]}
        imageAlts={[
          "Le champ où on entre son domaine pour lancer l’audit",
          "Les articles produits, avec leur score de qualité",
          "Le suivi des positions Google sur trente jours",
        ]}
      />

      {/* Product screen - l'ecran se redresse au scroll et le dashboard dedans
          est reellement cliquable (donnees de demo, aucun appel reseau). */}
      <section className="relative z-10 border-t border-white/5 overflow-hidden">
        <ContainerScroll
          titleComponent={
            <div className="px-6">
              <p className="text-xs font-mono uppercase tracking-wider text-emerald-400/80 mb-4">
                L'app en 3 secondes
              </p>
              <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
                Tout ton SEO,
                <br />
                <span className="text-emerald-400">une seule interface.</span>
              </h2>
              <p className="text-zinc-400 max-w-xl mx-auto">
                Liste d'articles, audit SEO automatique, suivi des positions Google. Clique dans l'écran, c'est le vrai produit.
              </p>
            </div>
          }
        >
          <DashboardDemo />
        </ContainerScroll>
      </section>

      {/* Workflow IA - 4-step animated flow */}
      <section className="relative z-10 border-t border-white/5 py-24 overflow-hidden">
        <div className="max-w-6xl mx-auto px-6">
          <Reveal className="text-center mb-14">
            <p className="text-xs font-mono uppercase tracking-wider text-emerald-400/80 mb-4">
              Le flow complet
            </p>
            <h2 className="text-4xl md:text-5xl font-bold tracking-tight mb-4">
              Du sujet à
              <br />
              <span className="text-emerald-400">l'article publié.</span>
            </h2>
            <p className="text-zinc-400 max-w-xl mx-auto">
              Tu donnes un mot-clé. 90 secondes plus tard, l'article est sur ton domaine, audité et indexé.
            </p>
          </Reveal>
          <Reveal delay={150}>
            <WorkflowIA3D />
          </Reveal>
        </div>
      </section>

      {/* What you get - 4 outcomes from the client's perspective */}
      <section className="relative z-10 border-t border-white/5 py-14 overflow-hidden">
        <div className="max-w-6xl mx-auto px-6">
          <p className="text-center text-[10px] font-mono uppercase tracking-[0.3em] text-zinc-600 mb-8">
            Ce que tu repars avec
          </p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {OUTCOMES.map((o, i) => (
              <Reveal key={o.title} delay={i * 80}>
                <div className="h-full rounded-xl border border-white/10 bg-zinc-900/40 p-5 hover:border-emerald-500/30 motion-safe:transition-colors">
                  <div className="text-3xl md:text-4xl font-bold tracking-tight text-emerald-400">
                    {o.metric}
                  </div>
                  <div className="mt-2 font-semibold text-zinc-100">{o.title}</div>
                  <div className="mt-1 text-xs text-zinc-500 leading-relaxed">{o.body}</div>
                </div>
              </Reveal>
            ))}
          </div>
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
              body="Application Password native WP 5.6+, aucun plugin à installer. Gridar synchronise tes articles existants et publie les nouveaux sur ton WordPress."
            />
          </Reveal>
          <Reveal delay={120}>
            <ModeCard
              icon={Newspaper}
              title="Pas encore de blog"
              tag="On t'en bâtit un"
              body="On héberge un blog Next.js sur ton sous-domaine blog.tonsite.ca. Schema FR-CA, sitemap, robots.txt, Core Web Vitals : tout est déjà configuré."
            />
          </Reveal>
          <Reveal delay={240}>
            <ModeCard
              icon={Zap}
              title="Site existant non-WP"
              tag="Wix, Shopify, custom"
              body="Cloudflare Worker, Vercel rewrites ou Nginx. On donne le snippet à coller chez ton hébergeur pour que /blog pointe vers Gridar."
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
            Brief, écriture, audit, suivi.
            <br />
            Un seul outil.
          </h2>
          <p className="mt-6 text-zinc-400 max-w-2xl mx-auto">
            24 outils dans un seul dashboard. Tu n&apos;achètes plus Ahrefs, Surfer et Frase à part.
          </p>
        </Reveal>

        {/* Phase 1 - Recherche */}
        <FeatureRow
          phase="01"
          icon={Search}
          title="Recherche stratégique"
          subtitle="Avant d'écrire, tu vois la structure, les FAQ, les entités et le word count des articles qui rankent déjà sur ta requête."
          features={[
            "Brief de contenu (intent + outline + FAQ + entités + EEAT)",
            "People Also Ask + schema FAQPage prêt à coller",
            "Questions Reddit / Quora dans le vocabulaire de tes lecteurs",
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
          subtitle="Claude rédige sur ton outline, avec ta voix et tes anecdotes. L'article sait que tu existes."
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
          subtitle="Après publication, Gridar suit tes positions Google chaque jour et te prévient quand un article commence à glisser."
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
                Surfer te sort un article avec "shopping" et "week-end" partout.
                Tes lecteurs lisent <em className="text-emerald-300 not-italic">magasinage</em> et{" "}
                <em className="text-emerald-300 not-italic">fin de semaine</em> au quotidien.
                Gridar écrit dans leur vocabulaire, pas celui d'un traducteur Parisien.
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
              Tarifs en CAD. Pas de piège SaaS.
            </h2>
          </Reveal>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 max-w-6xl mx-auto">
            <Reveal delay={0}>
              <PriceCard
                name="Essai"
                price="0$"
                period="pour toujours"
                hint="Sans carte"
                sites={1}
                features={[
                  "1 site",
                  "1 article / mois",
                  "Audit IA basique",
                  "Pas de suivi mots-clés",
                  "Support communauté",
                ]}
                cta="Commencer"
              />
            </Reveal>
            <Reveal delay={100}>
              <PriceCard
                name="Solo"
                price="29.99$"
                period="/mois"
                hint="Pour les solos"
                sites={1}
                features={[
                  "1 site",
                  "8 articles / mois",
                  "Audit IA + brief de contenu",
                  "Suivi 10 mots-clés + GSC",
                  "Lexique FR-CA",
                  "Rapport mensuel PDF",
                  "Support email <72h",
                ]}
                cta="Commencer Solo"
              />
            </Reveal>
            <Reveal delay={200}>
              <PriceCard
                name="Pro"
                price="89.99$"
                period="/mois"
                highlight
                hint="Le plus populaire"
                sites={2}
                features={[
                  "2 sites (WP, hébergé, externe)",
                  "60 articles / mois",
                  "24 outils SEO",
                  "Suivi 30 mots-clés + GSC + alertes",
                  "Audit bulk + topic clusters",
                  "Lexique FR-CA + EEAT + LocalBusiness",
                  "Rapport hebdomadaire PDF",
                  "API REST (30 req/h)",
                  "Support email <48h",
                ]}
                cta="Commencer Pro"
              />
            </Reveal>
            <Reveal delay={300}>
              <PriceCard
                name="Agence"
                price="199.99$"
                period="/mois"
                hint="Pour gérer 5 clients"
                sites={5}
                features={[
                  "5 sites",
                  "200 articles / mois",
                  "Tout du plan Pro",
                  "Comparaison multi-domaines",
                  "Suivi 100 mots-clés",
                  "API REST (200 req/h)",
                  "White-label optionnel",
                  "Onboarding personnalisé",
                  "Support prioritaire <8h",
                ]}
                cta="Choisir Agence"
              />
            </Reveal>
          </div>

          {/* Enterprise contact CTA */}
          <Reveal delay={400} className="max-w-6xl mx-auto mt-8">
            <div className="rounded-2xl border border-emerald-500/20 bg-gradient-to-r from-emerald-500/[0.06] to-transparent p-6 flex flex-col md:flex-row items-start md:items-center gap-4 justify-between">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono uppercase tracking-wider text-emerald-400">
                    Enterprise
                  </span>
                </div>
                <h3 className="text-lg font-semibold">
                  Plus de 5 sites, volume custom ou intégrations sur mesure ?
                </h3>
                <p className="text-sm text-zinc-400 mt-1">
                  SLA, comptable dédié, white-label complet, intégrations custom (CRM, n8n self-hosted, API privée). Contrat annuel.
                </p>
              </div>
              <a
                href="mailto:tokamdarius@gmail.com?subject=Plan%20Enterprise%20-%20demande%20sur%20mesure"
                className="shrink-0"
              >
                <Button
                  variant="outline"
                  className="bg-white/5 hover:bg-white/10 text-zinc-100 border-white/10"
                >
                  On en jase
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </a>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Guarantee - Hormozi-style stacked risk reversal */}
      <section className="relative z-10 py-24 border-t border-white/5">
        <div className="max-w-5xl mx-auto px-6">
          <Reveal className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-5">
              <ShieldCheck className="h-3 w-3" />
              Garantie triple Gridar
            </div>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight leading-[0.95]">
              Tu ne risques
              <br />
              <span className="text-emerald-400">absolument rien.</span>
            </h2>
            <p className="mt-6 text-zinc-400 max-w-2xl mx-auto text-base">
              On empile trois garanties pour que tu n'aies aucune raison de ne pas tester. Si Gridar ne livre pas, c'est nous qui payons - pas toi.
            </p>
          </Reveal>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Reveal delay={0}>
              <div className="h-full rounded-2xl border border-emerald-500/30 bg-gradient-to-b from-emerald-500/[0.08] to-transparent p-6">
                <div className="flex items-center gap-3 mb-4">
                  <span className="h-10 w-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-300 font-bold">1</span>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-emerald-300">Garantie qualité</div>
                </div>
                <h3 className="text-lg font-semibold mb-2">Premier article refait gratuitement</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Ton premier article ne te plaît pas ? On le re-génère gratuitement, autant de fois qu'il faut, jusqu'à ce qu'il sonne comme toi. Tant que c'est pas bon, on continue.
                </p>
              </div>
            </Reveal>

            <Reveal delay={120}>
              <div className="h-full rounded-2xl border border-emerald-500/30 bg-gradient-to-b from-emerald-500/[0.08] to-transparent p-6">
                <div className="flex items-center gap-3 mb-4">
                  <span className="h-10 w-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-300 font-bold">2</span>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-emerald-300">Garantie 30 jours</div>
                </div>
                <h3 className="text-lg font-semibold mb-2">Remboursement complet, sans question</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Pas convaincu après 30 jours ? Un courriel à <span className="text-zinc-200">tokamdarius@gmail.com</span>, on rembourse 100% en 48h. Tu gardes tous les articles publiés. Aucun frais d'annulation.
                </p>
              </div>
            </Reveal>

            <Reveal delay={240}>
              <div className="h-full rounded-2xl border border-emerald-500/30 bg-gradient-to-b from-emerald-500/[0.08] to-transparent p-6">
                <div className="flex items-center gap-3 mb-4">
                  <span className="h-10 w-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-300 font-bold">3</span>
                  <div className="text-[10px] font-mono uppercase tracking-wider text-emerald-300">Garantie 0 lock-in</div>
                </div>
                <h3 className="text-lg font-semibold mb-2">Tes articles t'appartiennent</h3>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Tout reste sur ton domaine, ton WordPress, ton compte Google. Si tu pars, tu pars avec tout. Aucun watermark, aucune dépendance, aucun lock-in technique.
                </p>
              </div>
            </Reveal>
          </div>

          <Reveal delay={400} className="mt-10 text-center">
            <p className="text-sm text-zinc-500">
              Conditions complètes :{" "}
              <Link href="/terms" className="text-zinc-300 underline underline-offset-2 hover:text-emerald-300">
                voir les CGU
              </Link>
              . Garantie applicable au premier abonnement par client.
            </p>
          </Reveal>
        </div>
      </section>

      {/* Integrations */}
      <section className="relative z-10 max-w-5xl mx-auto px-6 py-24 border-t border-white/5">
        <Reveal>
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs font-mono mb-4">
              <Zap className="h-3 w-3" />
              Intégrations
            </div>
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight">
              Génère des articles depuis n'importe où
            </h2>
            <p className="mt-4 text-lg text-zinc-400 max-w-2xl mx-auto">
              MCP server, node n8n, API REST. Branche Gridar à ton workflow et
              automatise la génération sans écrire une ligne de code custom.
            </p>
          </div>
        </Reveal>
        <Reveal>
          <div className="grid sm:grid-cols-3 gap-4">
            <Link
              href="/docs/integrations"
              className="group rounded-xl border border-white/10 p-6 hover:border-emerald-500/40 motion-safe:transition-all"
            >
              <Layers className="h-6 w-6 text-emerald-400 mb-3" />
              <div className="font-semibold text-zinc-100 mb-1">Claude / Cursor (MCP)</div>
              <p className="text-sm text-zinc-500">
                10 tools dans Claude Desktop, Claude Code, Cursor. "Génère un article sur
                X" et c'est fait.
              </p>
              <div className="mt-3 text-xs text-emerald-400 inline-flex items-center gap-1 group-hover:gap-2 motion-safe:transition-all">
                Voir le guide <ArrowRight className="h-3 w-3" />
              </div>
            </Link>
            <Link
              href="/docs/integrations"
              className="group rounded-xl border border-white/10 p-6 hover:border-emerald-500/40 motion-safe:transition-all"
            >
              <Zap className="h-6 w-6 text-emerald-400 mb-3" />
              <div className="font-semibold text-zinc-100 mb-1">n8n communautaire</div>
              <p className="text-sm text-zinc-500">
                Node officiel : Article, Audit, Brief, Keywords, Sites. Schedule trigger →
                article publié, sans toucher au code.
              </p>
              <div className="mt-3 text-xs text-emerald-400 inline-flex items-center gap-1 group-hover:gap-2 motion-safe:transition-all">
                Voir le guide <ArrowRight className="h-3 w-3" />
              </div>
            </Link>
            <Link
              href="/api-docs"
              className="group rounded-xl border border-white/10 p-6 hover:border-emerald-500/40 motion-safe:transition-all"
            >
              <Link2 className="h-6 w-6 text-emerald-400 mb-3" />
              <div className="font-semibold text-zinc-100 mb-1">API REST</div>
              <p className="text-sm text-zinc-500">
                Bearer token, JSON. Zapier, Make, GitHub Actions, scripts maison. 30
                req/h Pro, 200 req/h Agence.
              </p>
              <div className="mt-3 text-xs text-emerald-400 inline-flex items-center gap-1 group-hover:gap-2 motion-safe:transition-all">
                Référence API <ArrowRight className="h-3 w-3" />
              </div>
            </Link>
          </div>
        </Reveal>
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
        <Reveal className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-4xl md:text-6xl font-bold tracking-tight leading-[0.95]">
            Tes concurrents écrivent encore dans Word.
          </h2>
          <p className="mt-6 text-lg text-zinc-400">
            Toi tu auras un brief aligné sur le top 10 SERP, un article rédigé
            dans le vocabulaire de tes lecteurs, et un audit qui pointe quoi
            corriger ligne par ligne. 10 minutes par article.
          </p>
          <div className="mt-12 flex flex-col sm:flex-row gap-3 justify-center items-center">
            <Link href={authedHref}>
              <Button size="lg" className="w-full sm:w-auto bg-white text-zinc-950 hover:bg-zinc-200 h-12 px-8 text-base motion-safe:transition-transform motion-safe:duration-200 motion-safe:hover:-translate-y-0.5 motion-safe:hover:scale-[1.02]">
                {isAuthenticated ? "Aller au tableau de bord" : "Commencer gratuitement"}
              </Button>
            </Link>
            <span className="hidden sm:inline text-xs text-zinc-600 font-mono">ou</span>
            <a
              href="mailto:tokamdarius@gmail.com?subject=Demo%2015%20min%20-%20Gridar&body=Salut%20Darius%2C%0A%0AJ%27aimerais%20voir%20Gridar%20en%2015%20min.%20Mon%20site%20%3A%20%0AMa%20question%20%3A%20%0A%0AMerci%20%21"
              className="w-full sm:w-auto"
            >
              <Button
                size="lg"
                variant="outline"
                className="w-full sm:w-auto h-12 px-6 bg-transparent border-white/15 hover:bg-white/5 text-zinc-100 motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
              >
                Réserve 15 min avec Darius
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </a>
          </div>
          <p className="mt-5 text-xs text-zinc-500">
            Aucune carte requise · Annule en 1 clic · Garantie 30 jours
          </p>
        </Reveal>
      </section>

      {/* Footer cinematique : rideau plein ecran, meme composant que les
          pages d'outils, plan du site complet a l'interieur. */}
      <CinematicFooter />
    </div>
  );
}

// =========================================================================
// Sub-components
// =========================================================================

function HeroAuditInput({ authedHref }: { authedHref: string }) {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [domain, setDomain] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = domain.trim().replace(/^https?:\/\//i, "").replace(/\/.*$/, "");
    if (!clean) return;
    if (isAuthenticated) {
      router.push(authedHref);
      return;
    }
    setSubmitting(true);
    router.push(`/audit?domain=${encodeURIComponent(clean)}&autorun=1`);
  };

  return (
    <form
      onSubmit={onSubmit}
      className="relative flex flex-col sm:flex-row gap-2 p-1.5 rounded-2xl border border-white/10 bg-zinc-900/60 backdrop-blur-xl"
    >
      <input
        type="text"
        inputMode="url"
        autoComplete="off"
        spellCheck={false}
        placeholder="tondomaine.ca"
        value={domain}
        onChange={(e) => setDomain(e.target.value)}
        disabled={submitting}
        className="flex-1 bg-transparent px-4 py-3 text-base text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
        aria-label="Domaine à auditer"
      />
      <Button
        type="submit"
        size="lg"
        disabled={submitting || !domain.trim()}
        className="h-12 px-6 bg-gradient-to-r from-emerald-400 to-emerald-500 hover:from-emerald-300 hover:to-emerald-400 text-zinc-950 font-semibold motion-safe:transition-all motion-safe:hover:-translate-y-0.5 disabled:opacity-60"
      >
        <Search className="h-4 w-4 mr-2" />
        {submitting ? "Audit en cours..." : "Audite mon site"}
      </Button>
    </form>
  );
}

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
    </>
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
    <div className="group relative rounded-2xl border border-white/10 bg-zinc-900/40 hover:bg-zinc-900/60 hover:border-emerald-400/30 backdrop-blur-sm p-6 motion-safe:transition-all motion-safe:duration-300 motion-safe:hover:-translate-y-1 motion-safe:hover:shadow-[0_8px_30px_rgba(0,0,0,0.3)]">
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

function PlanSlots({
  filled,
  total,
  highlight,
}: {
  filled: number;
  total: number;
  highlight?: boolean;
}) {
  // Render up to 5 mini "site cards" + "+N" indicator if total > 5.
  const visible = Math.min(filled, 5);
  const overflow = filled > 5 ? filled - 5 : 0;
  const ghosts = Math.max(0, Math.min(total, 5) - visible);
  const cards: { active: boolean; rot: number }[] = [];
  for (let i = 0; i < visible; i++) {
    cards.push({ active: true, rot: -6 + i * 3 });
  }
  for (let i = 0; i < ghosts; i++) {
    cards.push({ active: false, rot: -6 + (visible + i) * 3 });
  }

  return (
    <div className="flex items-end justify-center gap-1 mb-4 h-12 select-none" aria-hidden>
      {cards.map((c, i) => (
        <div
          key={i}
          style={{
            transform: `rotate(${c.rot}deg) translateY(${Math.abs(c.rot) * 0.4}px)`,
            transition: "transform 0.4s",
          }}
          className={`w-6 h-9 rounded-[3px] border ${
            c.active
              ? highlight
                ? "bg-emerald-500/20 border-emerald-400/60"
                : "bg-zinc-700/60 border-zinc-600"
              : "bg-zinc-900/60 border-white/5"
          } flex flex-col p-[2px] gap-[1px]`}
        >
          <div
            className={`h-[2px] w-full rounded-full ${
              c.active
                ? highlight
                  ? "bg-emerald-400"
                  : "bg-zinc-500"
                : "bg-white/10"
            }`}
          />
          <div
            className={`h-[1px] w-3/4 rounded-full ${
              c.active ? (highlight ? "bg-emerald-400/60" : "bg-zinc-600") : "bg-white/5"
            }`}
          />
          <div
            className={`h-[1px] w-1/2 rounded-full ${
              c.active ? (highlight ? "bg-emerald-400/60" : "bg-zinc-600") : "bg-white/5"
            }`}
          />
        </div>
      ))}
      {overflow > 0 && (
        <div
          className={`ml-1 text-[10px] font-mono font-bold ${
            highlight ? "text-emerald-400" : "text-zinc-500"
          }`}
        >
          +{overflow}
        </div>
      )}
    </div>
  );
}

function PriceCard({
  name,
  price,
  period,
  hint,
  features,
  cta,
  highlight,
  sites,
}: {
  name: string;
  price: string;
  period: string;
  hint: string;
  features: string[];
  cta: string;
  highlight?: boolean;
  sites?: number;
}) {
  const { isAuthenticated } = useAuth();
  const ctaHref = isAuthenticated ? "/sites" : "/login";
  return (
    <div
      className={`relative rounded-2xl p-6 motion-safe:transition-all motion-safe:duration-300 motion-safe:hover:-translate-y-1 ${
        highlight
          ? "bg-gradient-to-b from-emerald-500/10 to-zinc-900/40 border-2 border-emerald-500/40 motion-safe:hover:shadow-[0_12px_40px_rgba(0,0,0,0.3)]"
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
      {typeof sites === "number" && (
        <PlanSlots filled={sites} total={10} highlight={highlight} />
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
      <Link href={ctaHref}>
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

// --- Client-perspective outcomes (replaces the old tech stack marquee) ----

const OUTCOMES: { metric: string; title: string; body: string }[] = [
  {
    metric: "10 min",
    title: "Par article publié",
    body: "Brief, écriture, audit, publication. Du sujet à la mise en ligne sur ton WordPress en moins de 10 minutes.",
  },
  {
    metric: "60 s",
    title: "Audit complet",
    body: "Tags, schema, vitesse mobile, positions Google, mots-clés manquants. Tout scanné en moins d'une minute.",
  },
  {
    metric: "FR-CA",
    title: "Lexique québécois",
    body: "Magasinage, fin de semaine, courriel. Tes lecteurs lisent leur vocabulaire, pas celui d'un traducteur parisien.",
  },
  {
    metric: "0 plugin",
    title: "Aucune install",
    body: "Application Password WP natif, proxy Cloudflare/Vercel pour les non-WP. Zéro code à toucher chez ton hébergeur.",
  },
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
    a: "Plan Essai : 1/mois. Solo : 8/mois. Pro : 60/mois. Agence : 200/mois. Au-delà, tu achètes des crédits à la pièce (5$ pour 5 articles).",
  },
  {
    q: "Et si je veux annuler ?",
    a: "Un clic dans tes paramètres. Pas de frais d'annulation. Tu gardes tes articles publiés (sur ton WP ou sur le blog hébergé que tu peux migrer).",
  },
];
