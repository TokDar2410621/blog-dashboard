/**
 * LandingRenderer.
 *
 * Renders a HostedLanding fetched from the API. Used by the catch-all
 * marketing route at app/[slug]/page.tsx. Layout:
 *   - Hero (h1 + subtitle + primary CTA)
 *   - Value props grid (icons mapped from lucide-react)
 *   - Body markdown (long-form SEO content rendered via react-markdown)
 *   - FAQ accordion (uses native <details>, also injects FAQPage JSON-LD)
 *   - Bottom CTA strip
 *   - Schema.org JSON-LD (Service / Product / WebPage + FAQPage when FAQ present)
 *
 * Same dark theme as the marketing landing page (zinc-950 + emerald accents)
 * so a HostedLanding visually belongs to gridar.app at first glance.
 */
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  AlertTriangle,
  ArrowRight,
  Award,
  BarChart3,
  Brain,
  CheckCircle2,
  ExternalLink,
  Eye,
  FileText,
  Gauge,
  Globe,
  Languages,
  Layers,
  LineChart,
  Link2,
  MapPin,
  PenLine,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Landing, ValueProp, FaqItem, SocialProofItem } from "@/lib/landing-api";

// Normalize a social-proof entry (string OR object) to a display string.
function socialProofText(item: SocialProofItem): string {
  if (typeof item === "string") return item;
  if (item && typeof item === "object") {
    return item.text || item.label || item.title || item.value || "";
  }
  return "";
}

// String -> icon map. Falls back to Sparkles. Keeps the model's `icon` field
// a free-form string while still type-safe at render time.
const ICONS: Record<string, LucideIcon> = {
  alerttriangle: AlertTriangle,
  award: Award,
  barchart3: BarChart3,
  brain: Brain,
  checkcircle2: CheckCircle2,
  externallink: ExternalLink,
  eye: Eye,
  filetext: FileText,
  gauge: Gauge,
  globe: Globe,
  languages: Languages,
  layers: Layers,
  linechart: LineChart,
  link2: Link2,
  mappin: MapPin,
  penline: PenLine,
  refreshcw: RefreshCw,
  search: Search,
  shieldcheck: ShieldCheck,
  sparkles: Sparkles,
  target: Target,
  trendingup: TrendingUp,
  zap: Zap,
};

function iconFor(name: string): LucideIcon {
  if (!name) return Sparkles;
  const key = name.replace(/[\s_-]/g, "").toLowerCase();
  return ICONS[key] || Sparkles;
}

// ---------------------------------------------------------------------------
// JSON-LD builders
// ---------------------------------------------------------------------------

function buildPrimaryJsonLd(landing: Landing, canonicalUrl: string) {
  // Honor any explicit schema_jsonld coming from the model first (admin
  // override). Otherwise build a sensible default for the schema_type.
  if (
    landing.schema_jsonld &&
    typeof landing.schema_jsonld === "object" &&
    "@type" in landing.schema_jsonld
  ) {
    return landing.schema_jsonld;
  }
  const base = {
    "@context": "https://schema.org",
    "@type": landing.schema_type || "WebPage",
    name: landing.h1 || landing.title,
    headline: landing.title,
    description: landing.meta_description || landing.hero_subtitle,
    url: canonicalUrl,
    inLanguage:
      landing.language === "fr"
        ? "fr-CA"
        : landing.language === "es"
        ? "es"
        : "en-CA",
  };
  if (landing.cover_image) {
    return { ...base, image: landing.cover_image };
  }
  return base;
}

function buildFaqJsonLd(faq: FaqItem[]) {
  if (!faq?.length) return null;
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faq.map((q) => ({
      "@type": "Question",
      name: q.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: q.answer,
      },
    })),
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LandingRenderer({
  landing,
  canonicalUrl,
}: {
  landing: Landing;
  canonicalUrl: string;
}) {
  const primaryJsonLd = buildPrimaryJsonLd(landing, canonicalUrl);
  const faqJsonLd = buildFaqJsonLd(landing.faq || []);
  const socialProofs = (landing.social_proof || [])
    .map(socialProofText)
    .filter((t) => t.trim().length > 0);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* JSON-LD injection. Two <script> tags so FAQPage stays separate. */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(primaryJsonLd) }}
      />
      {faqJsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
        />
      )}

      {/* Background grid */}
      <div
        aria-hidden
        className="fixed inset-0 z-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgb(255 255 255 / 1) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 1) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
      <div className="fixed inset-x-0 top-0 h-[40vh] z-0 pointer-events-none bg-gradient-to-b from-emerald-500/[0.05] via-transparent to-transparent" />

      {/* Hero */}
      <section className="relative z-10 max-w-4xl mx-auto px-6 pt-24 md:pt-32 pb-12 text-center">
        <h1 className="text-4xl md:text-6xl lg:text-7xl font-bold leading-[1.05] tracking-tight">
          {landing.h1}
        </h1>
        {landing.hero_subtitle && (
          <p className="mt-7 text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            {landing.hero_subtitle}
          </p>
        )}
        {landing.hero_cta_text && landing.hero_cta_url && (
          <div className="mt-10 flex justify-center">
            <Link href={landing.hero_cta_url}>
              <Button
                size="lg"
                className="bg-white text-zinc-950 hover:bg-zinc-200 h-12 px-7 text-base motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
              >
                <Sparkles className="h-4 w-4 mr-2" />
                {landing.hero_cta_text}
              </Button>
            </Link>
          </div>
        )}
      </section>

      {/* Social proof - trust signals band. Renders only when non-empty so
          landings without social_proof are visually unchanged. */}
      {socialProofs.length > 0 && (
        <section className="relative z-10 max-w-4xl mx-auto px-6 pb-2">
          <ul className="grid gap-3 sm:grid-cols-2">
            {socialProofs.map((text, i) => (
              <li
                key={i}
                className="flex items-start gap-3 rounded-lg border border-white/10 bg-zinc-900/40 px-4 py-3"
              >
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <span className="text-sm text-zinc-300 leading-relaxed">
                  {text}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Value props */}
      {landing.value_props?.length > 0 && (
        <section className="relative z-10 max-w-6xl mx-auto px-6 py-14 border-t border-white/5">
          <div
            className={`grid gap-4 ${
              landing.value_props.length >= 4
                ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
                : landing.value_props.length === 3
                ? "grid-cols-1 sm:grid-cols-3"
                : "grid-cols-1 sm:grid-cols-2"
            }`}
          >
            {landing.value_props.map((vp: ValueProp, i) => {
              const Icon = iconFor(vp.icon || "");
              return (
                <div
                  key={i}
                  className="rounded-xl border border-white/10 bg-zinc-900/40 p-5 hover:border-emerald-500/30 motion-safe:transition-colors"
                >
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mb-4">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="font-semibold text-zinc-100 mb-1">{vp.title}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed">
                    {vp.description}
                  </p>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Body markdown */}
      {landing.body_markdown && landing.body_markdown.trim().length > 0 && (
        <section className="relative z-10 max-w-3xl mx-auto px-6 py-16 border-t border-white/5">
          <article className="prose prose-invert prose-zinc max-w-none prose-headings:tracking-tight prose-h2:text-3xl prose-h2:mt-12 prose-h2:mb-4 prose-h3:text-xl prose-h3:mt-8 prose-h3:mb-3 prose-a:text-emerald-400 hover:prose-a:text-emerald-300 prose-strong:text-zinc-100 prose-li:my-1.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {landing.body_markdown}
            </ReactMarkdown>
          </article>
        </section>
      )}

      {/* FAQ */}
      {landing.faq?.length > 0 && (
        <section className="relative z-10 max-w-3xl mx-auto px-6 py-16 border-t border-white/5">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-center mb-12">
            Questions fréquentes
          </h2>
          <div className="space-y-3">
            {landing.faq.map((item, i) => (
              <details
                key={i}
                className="group border border-white/10 rounded-xl px-5 py-4 hover:border-white/20 motion-safe:transition-all motion-safe:duration-200 [&_summary::-webkit-details-marker]:hidden"
              >
                <summary className="cursor-pointer flex items-start justify-between gap-4 font-semibold">
                  <span>{item.question}</span>
                  <ArrowRight className="h-4 w-4 text-zinc-500 motion-safe:transition-transform motion-safe:duration-200 group-open:rotate-90 mt-1 shrink-0" />
                </summary>
                <p className="mt-4 text-sm text-zinc-400 leading-relaxed whitespace-pre-line">
                  {item.answer}
                </p>
              </details>
            ))}
          </div>
        </section>
      )}

      {/* Bottom CTA */}
      {landing.cta_bottom_text && landing.cta_bottom_url && (
        <section className="relative z-10 py-20 border-t border-white/5">
          <div className="max-w-3xl mx-auto px-6 text-center">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight leading-tight">
              Prêt à passer à l&apos;action&nbsp;?
            </h2>
            <p className="mt-5 text-zinc-400">
              {landing.hero_subtitle ||
                "Lance maintenant. Sans carte, sans engagement."}
            </p>
            <div className="mt-10">
              <Link href={landing.cta_bottom_url}>
                <Button
                  size="lg"
                  className="bg-white text-zinc-950 hover:bg-zinc-200 h-12 px-8 text-base motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
                >
                  <Sparkles className="h-4 w-4 mr-2" />
                  {landing.cta_bottom_text}
                </Button>
              </Link>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
