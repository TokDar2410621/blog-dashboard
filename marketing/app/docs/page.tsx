import type { Metadata } from "next";
import { DocsShell } from "@/components/DocsShell";
import { readDoc } from "@/lib/docs";

export const metadata: Metadata = {
  title: "Documentation Gridar",
  description:
    "Documentation produit Gridar : demarrage, connecter ton site, generation d'articles, outils SEO, plans, API REST, integrations MCP/n8n.",
  alternates: { canonical: "/docs" },
};

export default async function DocsIndex() {
  const content = await readDoc("");
  return <DocsShell slug="" content={content} />;
}
