/**
 * Catch-all route for HostedLanding pages served at the gridar.app root.
 *
 * Next.js App Router precedence: static routes (e.g. /audit, /docs, /blog,
 * /sitemap.xml, /privacy) take priority over this dynamic segment. So this
 * file only handles single-segment paths that do NOT match a static route -
 * exactly what we want for SEO landings like /audit-seo-gratuit-quebec.
 *
 * Flow:
 *   1. fetch /api/public/sites/<gridar>/landings/<slug>/ (ISR 1h)
 *   2. if 404 -> notFound() (standard Next.js 404 page)
 *   3. else render LandingRenderer with full payload + SEO metadata + JSON-LD
 */
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { LandingRenderer } from "@/components/LandingRenderer";
import { getLanding, listLandings } from "@/lib/landing-api";

const SITE_BASE = "https://gridar.app";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  try {
    const landing = await getLanding(slug);
    if (!landing) return { title: "Page introuvable" };
    const canonical = `${SITE_BASE}/${landing.slug}`;
    return {
      title: landing.title,
      description: landing.meta_description || landing.hero_subtitle,
      alternates: { canonical },
      openGraph: {
        title: landing.title,
        description: landing.meta_description || landing.hero_subtitle,
        url: canonical,
        type: "website",
        siteName: "Gridar",
        locale:
          landing.language === "fr"
            ? "fr_CA"
            : landing.language === "es"
            ? "es_ES"
            : "en_CA",
        images: landing.cover_image ? [{ url: landing.cover_image }] : [],
      },
      twitter: {
        card: "summary_large_image",
        title: landing.title,
        description: landing.meta_description || landing.hero_subtitle,
        images: landing.cover_image ? [landing.cover_image] : [],
      },
    };
  } catch {
    return { title: "Page introuvable" };
  }
}

// Static generation for every published landing at build time. Falls back to
// dynamic rendering for any slug not in the list (so newly-created landings
// don't 404 until the next build).
export async function generateStaticParams() {
  try {
    const landings = await listLandings();
    return landings.map((l) => ({ slug: l.slug }));
  } catch {
    return [];
  }
}

export const dynamicParams = true;

export default async function CatchAllLandingPage({ params }: Props) {
  const { slug } = await params;
  const landing = await getLanding(slug);
  if (!landing) {
    notFound();
  }
  const canonical = `${SITE_BASE}/${landing.slug}`;
  return <LandingRenderer landing={landing} canonicalUrl={canonical} />;
}
