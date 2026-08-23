import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";
import { BlogList } from "@/components/BlogList";
import { fetchBlogPosts } from "@/lib/blog-api";

export const metadata: Metadata = {
  title: "Blog Gridar - Tactiques SEO concrètes pour PME québécoises",
  description:
    "Articles SEO écrits, audités et publiés avec Gridar. Dogfooding pur. Lexique FR-CA, exemples québécois, sans bullshit marketing.",
  alternates: { canonical: "/blog" },
  openGraph: {
    title: "Blog Gridar",
    description: "Tactiques SEO QC écrites avec Gridar.",
    url: "https://www.gridar.app/blog",
    type: "website",
  },
};

// ISR: re-render the list at most once per hour. New articles published
// in the dashboard appear here within ~3600 seconds without a redeploy.
export const revalidate = 3600;

export default async function BlogIndexPage() {
  const posts = await fetchBlogPosts();

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-30 border-b border-white/5 bg-zinc-950/70 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
          <Link href="/">
            <Button
              variant="ghost"
              size="sm"
              className="-ml-2 text-zinc-400 hover:text-white hover:bg-white/5"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Accueil
            </Button>
          </Link>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-2">
            <GridarMark className="h-5 w-5" />
            <span className="font-semibold">Gridar</span>
            <span className="text-zinc-500 hidden sm:inline">/ Blog</span>
          </div>
          <div className="flex-1" />
          <Link href="/login">
            <Button size="sm" className="bg-white text-zinc-950 hover:bg-zinc-200">
              Commencer
            </Button>
          </Link>
        </div>
      </header>

      <section className="relative overflow-hidden border-b border-white/5">
        <div className="relative max-w-4xl mx-auto px-4 md:px-6 py-20 md:py-28 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-6">
            <Sparkles className="h-3 w-3" />
            Tactiques SEO QC
          </div>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight leading-[1.05] mb-5">
            Le blog{" "}
            <span className="bg-gradient-to-br from-emerald-300 via-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              Gridar
            </span>
            .
          </h1>
          <p className="text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            Tactiques SEO concrètes pour PME québécoises. Chaque article est
            rédigé, audité et publié avec Gridar. On dogfoode notre propre produit.
          </p>
        </div>
      </section>

      <main className="max-w-6xl mx-auto px-4 md:px-6 py-12">
        <BlogList posts={posts} />

        <section className="mt-24 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-10 md:p-12 text-center relative overflow-hidden">
          <div className="relative">
            <h2 className="text-3xl font-bold tracking-tight mb-3">
              Tu veux générer ce genre d&apos;article sur ton site ?
            </h2>
            <p className="text-zinc-400 mb-8 max-w-xl mx-auto">
              Gridar le fait pour toi. Du brief au déploiement WordPress, Shopify
              ou Webflow. Sans carte pour essayer.
            </p>
            <Link href="/login">
              <Button size="lg" className="bg-white text-zinc-950 hover:bg-zinc-200">
                <Sparkles className="h-4 w-4 mr-2" />
                Commencer gratuitement
              </Button>
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
