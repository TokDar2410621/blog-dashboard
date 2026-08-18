import type { Metadata } from "next";
import Link from "next/link";
import {
  Eye,
  Search,
  BarChart3,
  Target,
  TrendingUp,
  Quote,
  GitCompare,
  ArrowRight,
  Sparkles,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Outils SEO gratuits - Gridar",
  description:
    "Suite d'outils SEO gratuits : audit de site, visibilite IA, analyse de concurrents, difficulte de mots-cles, calculateur ROI. Sans inscription.",
  alternates: { canonical: "/tools" },
  openGraph: {
    title: "Outils SEO gratuits - Gridar",
    description:
      "Audit ton site, mesure ta visibilite dans ChatGPT et Gemini, trouve les mots-cles de tes concurrents. Gratuit, sans inscription.",
    url: "https://www.gridar.app/tools",
    type: "website",
  },
};

type ToolCard = {
  title: string;
  description: string;
  href: string;
  icon: React.ElementType;
  badge?: string;
  available: boolean;
};

const tools: ToolCard[] = [
  {
    title: "Audit SEO + GEO",
    description:
      "Score SEO complet, vitesse mobile, positions Google.ca et recommandations. En 30 secondes.",
    href: "/audit",
    icon: Search,
    badge: "Populaire",
    available: true,
  },
  {
    title: "AI Visibility Checker",
    description:
      "Decouvre si ChatGPT, Gemini et les moteurs IA recommandent ton entreprise ou tes concurrents.",
    href: "/tools/ai-visibility-checker",
    icon: Eye,
    available: true,
  },
  {
    title: "Competitor Gap Finder",
    description:
      "Trouve les mots-cles sur lesquels tes concurrents rankent mais pas toi. Identifie les opportunites manquees.",
    href: "/tools/competitor-gap",
    icon: GitCompare,
    available: true,
  },
  {
    title: "Can I Rank?",
    description:
      "Pas juste la difficulte du mot-cle. La difficulte pour TON site specifiquement.",
    href: "/tools/keyword-difficulty",
    icon: Target,
    available: true,
  },
  {
    title: "Calculateur ROI SEO",
    description:
      "Traduis ton potentiel SEO en visiteurs, leads, clients et revenus. Trois scenarios.",
    href: "/tools/seo-roi-calculator",
    icon: TrendingUp,
    available: true,
  },
  {
    title: "AI Citation Checker",
    description:
      "Est-ce que les moteurs IA utilisent ton site comme source? Decouvre quelles pages sont citees.",
    href: "/tools/ai-citation-checker",
    icon: Quote,
    available: true,
  },
  {
    title: "Comparaison de concurrents",
    description:
      "Compare ton site a ton principal concurrent sur 20+ dimensions SEO et decouvre comment le depasser.",
    href: "/tools/competitor-compare",
    icon: GitCompare,
    available: true,
  },
  {
    title: "Suivi de position Google",
    description:
      "Verifie ta position sur Google.ca pour un mot-cle specifique, geolocalise au Quebec.",
    href: "/suivi-position-google-canada",
    icon: BarChart3,
    available: true,
  },
];

export default function ToolsHubPage() {
  return (
    <div className="max-w-5xl mx-auto px-4 py-12 md:py-20">
      <div className="text-center max-w-2xl mx-auto mb-12">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300 mb-4">
          <Sparkles className="h-3 w-3" />
          <span>Gratuit, sans inscription</span>
        </div>
        <h1 className="text-3xl md:text-5xl font-bold tracking-tight mb-4">
          Outils SEO gratuits
        </h1>
        <p className="text-base md:text-lg text-zinc-400">
          Chaque outil te donne une vraie valeur immediate, te montre un
          probleme que tu ignorais, et te montre comment le corriger.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {tools.map((tool) => (
          <ToolCardComponent key={tool.href} tool={tool} />
        ))}
      </div>
    </div>
  );
}

function ToolCardComponent({ tool }: { tool: ToolCard }) {
  const Icon = tool.icon;
  const inner = (
    <div
      className={`group relative rounded-xl border p-6 transition-all duration-200 ${
        tool.available
          ? "border-white/10 bg-white/[0.02] hover:border-emerald-500/30 hover:bg-emerald-500/[0.03] cursor-pointer"
          : "border-white/5 bg-white/[0.01] opacity-60"
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
            <Icon className="h-5 w-5" />
          </div>
          <h2 className="text-lg font-semibold text-zinc-100">{tool.title}</h2>
        </div>
        {tool.badge && (
          <span
            className={`text-[10px] font-medium uppercase tracking-wider px-2 py-0.5 rounded-full ${
              tool.badge === "Populaire"
                ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
                : "bg-zinc-800 text-zinc-500 border border-zinc-700"
            }`}
          >
            {tool.badge}
          </span>
        )}
      </div>
      <p className="text-sm text-zinc-400 mb-4">{tool.description}</p>
      {tool.available && (
        <div className="flex items-center gap-1 text-sm font-medium text-emerald-400 group-hover:gap-2 transition-all">
          <span>Essayer gratuitement</span>
          <ArrowRight className="h-4 w-4" />
        </div>
      )}
    </div>
  );

  if (!tool.available) return inner;
  return <Link href={tool.href}>{inner}</Link>;
}
