/**
 * HostedLandingPage - catch-all route in App.tsx.
 *
 * Fetches a HostedLanding by slug from the public API and renders it.
 * If 404, redirects to "/" so the URL doesn't get stuck on a dead page.
 *
 * SEO: updates document.title + meta description + JSON-LD client-side.
 * Modern Googlebot renders JS so the JSON-LD picks up; for stronger SSR
 * the marketing/ Next.js variant (marketing/app/[slug]/page.tsx) covers
 * the same payload server-side once that deployment goes live.
 */
import { useEffect, useMemo } from "react";
import { Navigate, useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
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
  Loader2,
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
import {
  fetchPublicLanding,
  type PublicLanding,
  type ValueProp,
} from "@/lib/landing-public";

// String -> icon map. Falls back to Sparkles. Same set as the
// marketing/ renderer to keep authoring consistent.
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

// Update an existing <meta> tag or create one. Used for SPA SEO.
function setMetaTag(
  selector: string,
  attr: "name" | "property",
  attrValue: string,
  content: string,
) {
  let tag = document.head.querySelector<HTMLMetaElement>(selector);
  if (!tag) {
    tag = document.createElement("meta");
    tag.setAttribute(attr, attrValue);
    document.head.appendChild(tag);
  }
  tag.setAttribute("content", content);
}

function buildPrimaryJsonLd(
  landing: PublicLanding,
  canonicalUrl: string,
): Record<string, unknown> {
  if (
    landing.schema_jsonld &&
    typeof landing.schema_jsonld === "object" &&
    "@type" in landing.schema_jsonld
  ) {
    return landing.schema_jsonld;
  }
  const base: Record<string, unknown> = {
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
  if (landing.cover_image) base.image = landing.cover_image;
  return base;
}

function buildFaqJsonLd(landing: PublicLanding): Record<string, unknown> | null {
  if (!landing.faq?.length) return null;
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: landing.faq.map((q) => ({
      "@type": "Question",
      name: q.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: q.answer,
      },
    })),
  };
}

export default function HostedLandingPage() {
  const { slug } = useParams<{ slug: string }>();

  const { data, isLoading, isError } = useQuery<PublicLanding | null>({
    queryKey: ["public-landing", slug],
    queryFn: () => fetchPublicLanding(slug || ""),
    enabled: !!slug,
    staleTime: 60 * 60 * 1000,
    retry: 0,
  });

  const canonicalUrl = useMemo(
    () =>
      typeof window !== "undefined"
        ? `${window.location.origin}/${slug || ""}`
        : `https://gridar.app/${slug || ""}`,
    [slug],
  );

  // SEO + JSON-LD injection. Restores defaults on unmount so navigation
  // back to the home page doesn't keep the landing's title.
  useEffect(() => {
    if (!data) return;
    const prevTitle = document.title;
    const prevDesc =
      document.head
        .querySelector<HTMLMetaElement>('meta[name="description"]')
        ?.getAttribute("content") || "";

    document.title = data.title;
    setMetaTag(
      'meta[name="description"]',
      "name",
      "description",
      data.meta_description || data.hero_subtitle,
    );
    setMetaTag(
      'meta[property="og:title"]',
      "property",
      "og:title",
      data.title,
    );
    setMetaTag(
      'meta[property="og:description"]',
      "property",
      "og:description",
      data.meta_description || data.hero_subtitle,
    );
    setMetaTag(
      'meta[property="og:url"]',
      "property",
      "og:url",
      canonicalUrl,
    );

    // Canonical link.
    let canonicalLink =
      document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    const prevCanonical = canonicalLink?.getAttribute("href") || "";
    if (!canonicalLink) {
      canonicalLink = document.createElement("link");
      canonicalLink.setAttribute("rel", "canonical");
      document.head.appendChild(canonicalLink);
    }
    canonicalLink.setAttribute("href", canonicalUrl);

    // JSON-LD scripts. Tag them so we can clean up on unmount.
    const primary = document.createElement("script");
    primary.type = "application/ld+json";
    primary.dataset.landing = "primary";
    primary.text = JSON.stringify(buildPrimaryJsonLd(data, canonicalUrl));
    document.head.appendChild(primary);

    let faq: HTMLScriptElement | null = null;
    const faqJsonLd = buildFaqJsonLd(data);
    if (faqJsonLd) {
      faq = document.createElement("script");
      faq.type = "application/ld+json";
      faq.dataset.landing = "faq";
      faq.text = JSON.stringify(faqJsonLd);
      document.head.appendChild(faq);
    }

    return () => {
      document.title = prevTitle;
      if (prevDesc) {
        setMetaTag(
          'meta[name="description"]',
          "name",
          "description",
          prevDesc,
        );
      }
      if (prevCanonical && canonicalLink) {
        canonicalLink.setAttribute("href", prevCanonical);
      } else if (canonicalLink && canonicalLink.parentNode) {
        canonicalLink.parentNode.removeChild(canonicalLink);
      }
      primary.remove();
      if (faq) faq.remove();
    };
  }, [data, canonicalUrl]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-emerald-400" />
      </div>
    );
  }

  if (isError || !data) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Background grid + top fade, matching the marketing landing. */}
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
          {data.h1}
        </h1>
        {data.hero_subtitle && (
          <p className="mt-7 text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            {data.hero_subtitle}
          </p>
        )}
        {data.hero_cta_text && data.hero_cta_url && (
          <div className="mt-10 flex justify-center">
            <Link to={data.hero_cta_url}>
              <Button
                size="lg"
                className="bg-white text-zinc-950 hover:bg-zinc-200 h-12 px-7 text-base"
              >
                <Sparkles className="h-4 w-4 mr-2" />
                {data.hero_cta_text}
              </Button>
            </Link>
          </div>
        )}
      </section>

      {/* Value props */}
      {data.value_props?.length > 0 && (
        <section className="relative z-10 max-w-6xl mx-auto px-6 py-14 border-t border-white/5">
          <div
            className={`grid gap-4 ${
              data.value_props.length >= 4
                ? "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4"
                : data.value_props.length === 3
                ? "grid-cols-1 sm:grid-cols-3"
                : "grid-cols-1 sm:grid-cols-2"
            }`}
          >
            {data.value_props.map((vp: ValueProp, i) => {
              const Icon = iconFor(vp.icon || "");
              return (
                <div
                  key={i}
                  className="rounded-xl border border-white/10 bg-zinc-900/40 p-5 hover:border-emerald-500/30 transition-colors"
                >
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 mb-4">
                    <Icon className="h-5 w-5" />
                  </span>
                  <h3 className="font-semibold text-zinc-100 mb-1">
                    {vp.title}
                  </h3>
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
      {data.body_markdown && data.body_markdown.trim().length > 0 && (
        <section className="relative z-10 max-w-3xl mx-auto px-6 py-16 border-t border-white/5">
          <article className="prose prose-invert prose-zinc max-w-none prose-headings:tracking-tight prose-h2:text-3xl prose-h2:mt-12 prose-h2:mb-4 prose-h3:text-xl prose-h3:mt-8 prose-h3:mb-3 prose-a:text-emerald-400 hover:prose-a:text-emerald-300 prose-strong:text-zinc-100 prose-li:my-1.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {data.body_markdown}
            </ReactMarkdown>
          </article>
        </section>
      )}

      {/* FAQ */}
      {data.faq?.length > 0 && (
        <section className="relative z-10 max-w-3xl mx-auto px-6 py-16 border-t border-white/5">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight text-center mb-12">
            Questions fréquentes
          </h2>
          <div className="space-y-3">
            {data.faq.map((item, i) => (
              <details
                key={i}
                className="group border border-white/10 rounded-xl px-5 py-4 hover:border-white/20 [&_summary::-webkit-details-marker]:hidden"
              >
                <summary className="cursor-pointer flex items-start justify-between gap-4 font-semibold">
                  <span>{item.question}</span>
                  <ArrowRight className="h-4 w-4 text-zinc-500 transition-transform group-open:rotate-90 mt-1 shrink-0" />
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
      {data.cta_bottom_text && data.cta_bottom_url && (
        <section className="relative z-10 py-20 border-t border-white/5">
          <div className="max-w-3xl mx-auto px-6 text-center">
            <h2 className="text-3xl md:text-5xl font-bold tracking-tight leading-tight">
              Prêt à passer à l&apos;action&nbsp;?
            </h2>
            <p className="mt-5 text-zinc-400">
              {data.hero_subtitle ||
                "Lance maintenant. Sans carte, sans engagement."}
            </p>
            <div className="mt-10">
              <Link to={data.cta_bottom_url}>
                <Button
                  size="lg"
                  className="bg-white text-zinc-950 hover:bg-zinc-200 h-12 px-8 text-base"
                >
                  <Sparkles className="h-4 w-4 mr-2" />
                  {data.cta_bottom_text}
                </Button>
              </Link>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
