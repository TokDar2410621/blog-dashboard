import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Sparkles,
  Languages,
  Globe,
  CheckCircle2,
  ArrowRight,
  Newspaper,
  Search,
  PenLine,
  BarChart3,
  Zap,
  ChevronRight,
} from "lucide-react";

export default function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Top nav */}
      <header className="border-b">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Newspaper className="h-6 w-6 text-primary" />
            <span className="font-bold text-lg">Blog Dashboard</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="text-sm hover:text-primary"
            >
              Connexion
            </Link>
            <Link to="/login">
              <Button size="sm">Commencer gratuitement</Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 py-20 md:py-32">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-mono uppercase tracking-wider mb-6">
            <Sparkles className="h-3 w-3" />
            Bilingue FR-CA · IA · 100% pour le Québec
          </div>
          <h1 className="text-5xl md:text-7xl font-bold leading-tight tracking-tight">
            Le SEO en français qui comprend le Québec.
          </h1>
          <p className="mt-6 text-xl text-muted-foreground max-w-2xl leading-relaxed">
            Ahrefs et Semrush sont en anglais et coûtent 200$ US/mois. Nous, on
            génère, audite et optimise tes articles en FR-CA, sans accent de
            France. Pour les PME québécoises qui veulent enfin ranker.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-3">
            <Link to="/login">
              <Button size="lg" className="w-full sm:w-auto">
                <Sparkles className="h-4 w-4 mr-2" />
                Connecter mon site WordPress
              </Button>
            </Link>
            <a href="#pricing">
              <Button size="lg" variant="outline" className="w-full sm:w-auto">
                Voir les tarifs
              </Button>
            </a>
          </div>
          <p className="mt-4 text-xs text-muted-foreground">
            Essai gratuit · Aucune carte requise · 2 minutes pour connecter
          </p>
        </div>
      </section>

      {/* Social proof / mode flexibility */}
      <section className="max-w-6xl mx-auto px-6 py-12 border-y">
        <p className="text-center text-sm font-mono uppercase tracking-wider text-muted-foreground mb-8">
          Ton site existe déjà ? On s&apos;y connecte. Pas encore ? On t&apos;en bâtit un.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card>
            <CardContent className="pt-6 space-y-2">
              <div className="flex items-center gap-2">
                <Globe className="h-5 w-5 text-primary" />
                <h3 className="font-semibold">WordPress</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Connecte ton WP en 2 minutes via Application Password (natif WP 5.6+, aucun plugin à installer).
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 space-y-2">
              <div className="flex items-center gap-2">
                <Newspaper className="h-5 w-5 text-primary" />
                <h3 className="font-semibold">Pas de blog ? On en bâtit un.</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                On te livre un blog Next.js complet, hébergé chez nous, sur ton sous-domaine
                <code className="text-xs px-1 rounded bg-muted ml-1">blog.tonsite.ca</code>.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6 space-y-2">
              <div className="flex items-center gap-2">
                <Zap className="h-5 w-5 text-primary" />
                <h3 className="font-semibold">Site existant non-WP</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Cloudflare Worker, Vercel rewrites, Nginx — guides clé-en-main pour servir le blog sous{" "}
                <code className="text-xs px-1 rounded bg-muted">tonsite.ca/blog</code>.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Features — 3 phases */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold tracking-tight">
            Le parcours SEO complet, du brief au ranking
          </h2>
          <p className="mt-4 text-muted-foreground max-w-2xl mx-auto">
            24 outils intégrés. Tu n&apos;as plus besoin de jongler entre Ahrefs, Surfer, Frase et Originality.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Phase 1 — Recherche */}
          <Card className="border-primary/20">
            <CardContent className="pt-6 space-y-4">
              <div className="flex items-center gap-2">
                <Search className="h-6 w-6 text-primary" />
                <h3 className="font-bold text-lg">1 · Recherche</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Avant d&apos;écrire, on t&apos;équipe avec ce que tes concurrents top SERP ont dans la tête.
              </p>
              <ul className="space-y-2 text-sm">
                {[
                  "Brief de contenu (intent + outline + FAQ + entités + EEAT)",
                  "People Also Ask de Google + schema FAQPage prêt à coller",
                  "Questions Reddit + Quora — la vraie phrasing de tes lecteurs",
                  "Google Trends FR-CA avec graphique 12 mois",
                  "Recherche de mots-clés (Serper + Gemini)",
                  "Top 10 SERP + concurrents avec word count médian",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          {/* Phase 2 — Génération */}
          <Card className="border-primary/20">
            <CardContent className="pt-6 space-y-4">
              <div className="flex items-center gap-2">
                <PenLine className="h-6 w-6 text-primary" />
                <h3 className="font-bold text-lg">2 · Génération</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Claude écrit en suivant TON brief, en lexique québécois, avec ta voix.
              </p>
              <ul className="space-y-2 text-sm">
                {[
                  "Article complet en suivant l'outline du brief",
                  "Knowledge base personnelle (ta voix, anecdotes, ton)",
                  "Lexique québécois auto (week-end → fin de semaine)",
                  "Anti-cannibalisation (refuse les doublons)",
                  "Traduction FR ↔ EN ↔ ES, statuts mirroirs",
                  "Génération inline pour rééditer une section",
                  "Schema.org Article + Person EEAT auto-injecté",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          {/* Phase 3 — Optimisation */}
          <Card className="border-primary/20">
            <CardContent className="pt-6 space-y-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-6 w-6 text-primary" />
                <h3 className="font-bold text-lg">3 · Optimisation</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                Audit, suivi, alertes. On garde ton blog vivant et ranké.
              </p>
              <ul className="space-y-2 text-sm">
                {[
                  "Audit IA (per-article + bulk site-wide)",
                  "Lisibilité Flesch-Kincaid FR/EN en live",
                  "Suivi positions Google quotidien (graphe 90j)",
                  "Détection de déclin via GSC + alertes",
                  "Topic clusters (pillars + spokes)",
                  "Maillage interne (orphelins, hubs, dead-ends)",
                  "Liens cassés (404, timeout, redirects 301 auto)",
                  "Hreflang multi-langue + rapport hebdomadaire PDF",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* Quebec differentiator */}
      <section className="max-w-6xl mx-auto px-6 py-20 border-y">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-center">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-mono uppercase tracking-wider mb-4">
              <Languages className="h-3 w-3" />
              Le différenciant Québec
            </div>
            <h2 className="text-4xl font-bold tracking-tight">
              Pas un Ahrefs traduit en français de France.
            </h2>
            <p className="mt-6 text-lg text-muted-foreground">
              Surfer écrit "shopping". Frase écrit "week-end". Ahrefs écrit "parking". Tes lecteurs québécois sont allergiques. Nous, on connaît la différence entre <em>magasiner</em>, <em>fin de semaine</em>, <em>stationnement</em> et <em>courriel</em>.
            </p>
            <ul className="mt-6 space-y-3">
              {[
                ["Lexique FR-CA intégré", "50+ termes France→Québec auto-détectés"],
                ["Schema LocalBusiness québécois", "addressRegion=QC, areaServed=Québec, conventions OQLF"],
                ["Géo-localisation FR-CA dans Google Trends", "tendances réelles du marché québécois"],
                ["EEAT bilingue", "JSON-LD Person en FR avec credentials adaptés"],
              ].map(([title, desc]) => (
                <li key={title} className="flex items-start gap-3">
                  <Languages className="h-4 w-4 text-primary shrink-0 mt-1" />
                  <div>
                    <div className="font-semibold">{title}</div>
                    <div className="text-sm text-muted-foreground">{desc}</div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-card border rounded-lg p-6 font-mono text-sm space-y-3">
            <div className="text-xs text-muted-foreground uppercase tracking-wider">
              Lexique québécois en action
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="line-through text-muted-foreground">shopping</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                <span className="text-green-600">magasinage</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="line-through text-muted-foreground">week-end</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                <span className="text-green-600">fin de semaine</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="line-through text-muted-foreground">parking</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                <span className="text-green-600">stationnement</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="line-through text-muted-foreground">email</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                <span className="text-green-600">courriel</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="line-through text-muted-foreground">login</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                <span className="text-green-600">identifiant</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="line-through text-muted-foreground">startup</span>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
                <span className="text-green-600">jeune pousse</span>
              </div>
              <div className="text-xs text-muted-foreground pt-3 border-t">
                + 44 autres termes auto-détectés en live dans l&apos;éditeur.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold tracking-tight">Tarifs simples</h2>
          <p className="mt-4 text-muted-foreground">
            Aucun lock-in. Annule en un clic. Tarifs en CAD.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
          {/* Free tier */}
          <Card>
            <CardContent className="pt-6 space-y-4">
              <div>
                <h3 className="font-bold text-lg">Essai</h3>
                <p className="text-sm text-muted-foreground">
                  Découvre l&apos;outil sans risque
                </p>
              </div>
              <div>
                <div className="text-4xl font-bold">0$</div>
                <div className="text-sm text-muted-foreground">pour toujours</div>
              </div>
              <ul className="space-y-2 text-sm">
                {[
                  "1 site",
                  "5 articles générés/mois",
                  "Audit IA basique",
                  "Brief de contenu",
                  "Suivi 5 mots-clés",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <Link to="/login">
                <Button variant="outline" className="w-full">
                  Commencer
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Pro tier */}
          <Card className="border-primary border-2 relative">
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-primary text-primary-foreground text-xs font-mono uppercase tracking-wider">
              Le plus populaire
            </div>
            <CardContent className="pt-6 space-y-4">
              <div>
                <h3 className="font-bold text-lg">Pro</h3>
                <p className="text-sm text-muted-foreground">
                  Pour les PME qui ranken sérieusement
                </p>
              </div>
              <div>
                <div className="text-4xl font-bold">79$</div>
                <div className="text-sm text-muted-foreground">par mois</div>
              </div>
              <ul className="space-y-2 text-sm">
                {[
                  "3 sites (WP, hébergé, externe)",
                  "Articles illimités",
                  "Tous les outils SEO (24)",
                  "Suivi 50 mots-clés + GSC + alertes",
                  "Audit bulk + topic clusters",
                  "Lexique FR-CA + EEAT + LocalBusiness",
                  "Rapport hebdomadaire PDF",
                  "Support email <24h",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <Link to="/login">
                <Button className="w-full">
                  Commencer Pro
                </Button>
              </Link>
            </CardContent>
          </Card>

          {/* Agency tier */}
          <Card>
            <CardContent className="pt-6 space-y-4">
              <div>
                <h3 className="font-bold text-lg">Agence</h3>
                <p className="text-sm text-muted-foreground">
                  Pour gérer plusieurs clients
                </p>
              </div>
              <div>
                <div className="text-4xl font-bold">199$</div>
                <div className="text-sm text-muted-foreground">par mois</div>
              </div>
              <ul className="space-y-2 text-sm">
                {[
                  "10 sites",
                  "Tout du plan Pro",
                  "Comparaison multi-domaines",
                  "Suivi 200 mots-clés",
                  "White-label optionnel",
                  "Onboarding personnalisé 1×",
                  "Support prioritaire <4h",
                ].map((item) => (
                  <li key={item} className="flex items-start gap-2">
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <Link to="/login">
                <Button variant="outline" className="w-full">
                  Choisir Agence
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>

        <p className="text-center text-sm text-muted-foreground mt-8">
          Besoin de plus de 10 sites ou d&apos;une intégration custom ?{" "}
          <a href="mailto:tokamdarius@gmail.com" className="text-primary hover:underline">
            Parle-moi
          </a>
          .
        </p>
      </section>

      {/* FAQ */}
      <section className="max-w-3xl mx-auto px-6 py-20 border-t">
        <h2 className="text-3xl font-bold tracking-tight text-center mb-12">
          Questions fréquentes
        </h2>
        <div className="space-y-4">
          {[
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
              a: "Non si tu nous donnes ta knowledge base personnelle (ta voix, tes anecdotes). Le brief stratégique force Claude à suivre une structure unique par article. On intègre aussi des signaux EEAT (auteur réel, credentials, dates) que Google récompense.",
            },
            {
              q: "Combien d'articles puis-je générer par mois ?",
              a: "Plan Essai : 5/mois. Plans Pro et Agence : illimité. Le seul vrai coût pour nous c'est l'API Claude — on absorbe ça dans le prix.",
            },
            {
              q: "Et si je veux annuler ?",
              a: "Un clic dans tes paramètres. Pas de frais d'annulation. Tu gardes tes articles publiés (sur ton WP ou sur le blog hébergé que tu peux migrer).",
            },
          ].map((item, i) => (
            <details
              key={i}
              className="border rounded-lg p-4 [&_summary::-webkit-details-marker]:hidden"
            >
              <summary className="cursor-pointer flex items-center justify-between font-semibold">
                <span>{item.q}</span>
                <ChevronRight className="h-4 w-4 transition-transform [details[open]_&]:rotate-90" />
              </summary>
              <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                {item.a}
              </p>
            </details>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="max-w-4xl mx-auto px-6 py-20 text-center">
        <h2 className="text-4xl md:text-5xl font-bold tracking-tight">
          Tes concurrents québécois utilisent encore Word et ChatGPT.
        </h2>
        <p className="mt-6 text-lg text-muted-foreground">
          Toi tu auras un Brief stratégique aligné sur le SERP, un article que
          Claude rédige en lexique québécois, et un audit IA qui te dit
          exactement quoi corriger. En 10 minutes par article.
        </p>
        <div className="mt-10 flex flex-col sm:flex-row gap-3 justify-center">
          <Link to="/login">
            <Button size="lg">
              <Sparkles className="h-4 w-4 mr-2" />
              Commencer gratuitement
            </Button>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t mt-16">
        <div className="max-w-6xl mx-auto px-6 py-10 text-sm text-muted-foreground">
          <div className="flex flex-col md:flex-row justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Newspaper className="h-5 w-5 text-primary" />
                <span className="font-bold text-foreground">Blog Dashboard</span>
              </div>
              <p className="max-w-md">
                Le SaaS SEO bilingue FR-CA, conçu et opéré au Québec, pour les
                PME québécoises. Aucun investisseur, aucun pivot prévu.
              </p>
            </div>
            <div className="flex flex-wrap gap-6">
              <a href="mailto:tokamdarius@gmail.com" className="hover:text-primary">
                Contact
              </a>
              <Link to="/login" className="hover:text-primary">
                Connexion
              </Link>
              <a href="#pricing" className="hover:text-primary">
                Tarifs
              </a>
              <a
                href="https://github.com/TokDar2410621/blog-dashboard"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary"
              >
                GitHub
              </a>
            </div>
          </div>
          <div className="mt-8 pt-6 border-t text-xs">
            © {new Date().getFullYear()} Blog Dashboard · Fait à Saint-Hyacinthe, QC.
          </div>
        </div>
      </footer>
    </div>
  );
}
