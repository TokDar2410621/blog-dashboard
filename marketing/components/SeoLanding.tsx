import type { ReactNode } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { MarketingHeader } from "@/components/MarketingHeader";
import { MarketingFooter } from "@/components/MarketingFooter";
import { Button } from "@/components/ui/button";

/**
 * Squelette commun des landings SEO écrites à la main.
 *
 * Pourquoi il existe : le gabarit hero + bénéfices + article + FAQ + CTA était
 * recopié en entier dans chaque page. À une page, c'est acceptable ; à six,
 * chaque correction d'accessibilité ou de balisage devait être refaite six
 * fois, et la sixième était toujours oubliée. Le contenu reste dans la page,
 * la structure vit ici.
 *
 * La FAQ est une source de vérité unique : la même liste alimente la section
 * visible et le JSON-LD FAQPage. Un balisage qui promet une question absente
 * de la page est une raison de perte d'éligibilité aux résultats enrichis.
 */

export interface FaqItem {
  question: string;
  answer: string;
}

export interface Benefit {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  text: string;
}

export interface LandingCta {
  href: string;
  label: string;
}

export function SeoLanding({
  trail,
  badge,
  badgeIcon: BadgeIcon,
  h1,
  lede,
  ctaPrimary,
  ctaSecondary,
  benefitsTitle,
  benefits,
  faqTitle,
  faq,
  finalCtaTitle,
  finalCtaText,
  finalCtaPrimary,
  finalCtaSecondary,
  jsonLd,
  children,
}: {
  trail: string;
  badge: string;
  badgeIcon: React.ComponentType<{ className?: string }>;
  h1: string;
  lede: string;
  ctaPrimary: LandingCta;
  ctaSecondary: LandingCta;
  benefitsTitle: string;
  benefits: Benefit[];
  faqTitle: string;
  faq: FaqItem[];
  finalCtaTitle: string;
  finalCtaText: string;
  finalCtaPrimary: LandingCta;
  finalCtaSecondary: LandingCta;
  /** Objet Service (ou équivalent) propre à la page. Le FAQPage est dérivé de `faq`. */
  jsonLd: Record<string, unknown>;
  children: ReactNode;
}) {
  const faqJsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faq.map((item) => ({
      "@type": "Question",
      name: item.question,
      acceptedAnswer: { "@type": "Answer", text: item.answer },
    })),
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />

      <MarketingHeader trail={trail} />

      <main className="relative z-10">
        {/* 1. HERO */}
        <section className="max-w-4xl mx-auto px-4 md:px-6 pt-14 pb-8 text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/[0.06] px-3 py-1 text-xs text-emerald-300">
            <BadgeIcon className="h-3.5 w-3.5" />
            {badge}
          </span>
          <h1 className="mt-5 text-3xl md:text-5xl font-bold tracking-tight text-zinc-50">
            {h1}
          </h1>
          <p className="mt-5 text-lg md:text-xl text-zinc-300 max-w-2xl mx-auto">
            {lede}
          </p>
          <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              asChild
              size="lg"
              className="bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold"
            >
              <Link href={ctaPrimary.href}>
                {ctaPrimary.label}
                <ArrowRight className="h-4 w-4 ml-2" />
              </Link>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="border-white/15 text-zinc-200 hover:bg-white/5"
            >
              <Link href={ctaSecondary.href}>{ctaSecondary.label}</Link>
            </Button>
          </div>
        </section>

        {/* 2. BÉNÉFICES */}
        <section className="max-w-5xl mx-auto px-4 md:px-6 py-16">
          <h2 className="text-center text-2xl md:text-3xl font-bold text-zinc-50 mb-10">
            {benefitsTitle}
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {benefits.map((b) => {
              const Icon = b.icon;
              return (
                <div
                  key={b.title}
                  className="rounded-xl border border-white/10 bg-white/[0.02] p-5"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 mb-3">
                    <Icon className="h-5 w-5 text-emerald-400" />
                  </div>
                  <h3 className="font-semibold text-zinc-100 mb-1.5">{b.title}</h3>
                  <p className="text-sm text-zinc-400 leading-relaxed">{b.text}</p>
                </div>
              );
            })}
          </div>
        </section>

        {/* 3. CONTENU */}
        <section className="max-w-3xl mx-auto px-4 md:px-6 pb-16">
          <article
            className="prose prose-invert max-w-none
                       prose-headings:text-zinc-100 prose-headings:tracking-tight
                       prose-h2:mt-12 prose-h2:border-t prose-h2:border-white/10 prose-h2:pt-8 prose-h2:text-2xl
                       prose-h3:text-xl prose-h3:text-zinc-100
                       prose-p:text-zinc-300 prose-li:text-zinc-300
                       prose-strong:text-zinc-100
                       prose-a:text-emerald-400 prose-a:no-underline hover:prose-a:text-emerald-300 hover:prose-a:underline"
          >
            {children}
          </article>
        </section>

        {/* 4. FAQ */}
        <section className="max-w-3xl mx-auto px-4 md:px-6 pb-16">
          <h2 className="text-2xl md:text-3xl font-bold text-zinc-50 mb-8 text-center">
            {faqTitle}
          </h2>
          <div className="space-y-3">
            {faq.map((item) => (
              <details
                key={item.question}
                className="group rounded-xl border border-white/10 bg-white/[0.02] p-5"
              >
                <summary className="cursor-pointer list-none font-semibold text-zinc-100 flex items-center justify-between gap-4">
                  {item.question}
                  <span className="text-emerald-400 transition-transform group-open:rotate-45 text-xl leading-none">
                    +
                  </span>
                </summary>
                <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
                  {item.answer}
                </p>
              </details>
            ))}
          </div>
        </section>

        {/* 5. CTA FINAL */}
        <section className="max-w-3xl mx-auto px-4 md:px-6 pb-20">
          <div className="rounded-2xl border border-emerald-500/30 bg-gradient-to-b from-emerald-500/[0.08] to-transparent p-8 md:p-10 text-center">
            <h2 className="text-2xl md:text-3xl font-bold text-zinc-50">
              {finalCtaTitle}
            </h2>
            <p className="mt-4 text-zinc-300 max-w-xl mx-auto">{finalCtaText}</p>
            <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                asChild
                size="lg"
                className="bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold"
              >
                <Link href={finalCtaPrimary.href}>
                  {finalCtaPrimary.label}
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 hover:text-emerald-200"
              >
                <Link href={finalCtaSecondary.href}>{finalCtaSecondary.label}</Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
