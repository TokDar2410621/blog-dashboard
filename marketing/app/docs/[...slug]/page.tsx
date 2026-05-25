import type { Metadata } from "next";
import { DocsShell } from "@/components/DocsShell";
import { listDocSlugs, readDoc } from "@/lib/docs";

type PageProps = {
  params: Promise<{ slug: string[] }>;
};

export async function generateStaticParams() {
  const slugs = await listDocSlugs();
  return slugs
    .filter((s) => s.length > 0)
    .map((s) => ({ slug: s.split("/") }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const joined = slug.join("/");
  const content = await readDoc(joined);
  if (!content) {
    return { title: "Page introuvable", robots: { index: false, follow: false } };
  }
  // First non-empty markdown H1 wins as title fallback.
  const h1Match = content.match(/^#\s+(.+?)\s*$/m);
  const title = h1Match ? h1Match[1] : `Docs : ${joined}`;
  const firstParagraph = content
    .replace(/^---[\s\S]*?---/, "")
    .split(/\n\s*\n/)
    .find((b) => b.trim() && !b.trim().startsWith("#"));
  const description = firstParagraph
    ? firstParagraph.replace(/[`*_>]/g, "").trim().slice(0, 160)
    : "Documentation Gridar.";
  return {
    title,
    description,
    alternates: { canonical: `/docs/${joined}` },
  };
}

export default async function DocPage({ params }: PageProps) {
  const { slug } = await params;
  const joined = slug.join("/");
  const content = await readDoc(joined);
  return <DocsShell slug={joined} content={content} />;
}
