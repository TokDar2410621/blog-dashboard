import type { Metadata } from "next";
import { ConnectorPage } from "@/components/ConnectorPage";

export const metadata: Metadata = {
  title: "Connecteur MCP de Gridar - le SEO dans ton IA",
  description:
    "Branche les outils SEO de Gridar (audit, positions Google, mots-cles, visibilite IA) directement dans ChatGPT, Claude, Cursor et Claude Code via le serveur MCP mcp.gridar.app/mcp.",
  alternates: { canonical: "/mcp" },
  openGraph: {
    title: "Connecteur MCP de Gridar",
    description:
      "Le SEO de Gridar directement dans ChatGPT, Claude, Cursor et Claude Code. Serveur MCP distant, connexion OAuth.",
    url: "https://www.gridar.app/mcp",
    type: "website",
  },
};

export default function McpConnectorPage() {
  return (
    <ConnectorPage
      eyebrow="Connecteur MCP"
      title="Le SEO de Gridar, directement dans ton IA"
      subtitle="Gridar expose ses outils SEO comme un serveur MCP distant. Branche-le dans ChatGPT, Claude, Cursor ou Claude Code, et ton assistant audite ton site, suit tes positions Google et trouve tes mots-cles, sans quitter la conversation."
      steps={[
        {
          title: "Copie l'URL du serveur",
          body: "C'est un serveur MCP distant (Streamable HTTP), rien a installer sur ta machine.",
        },
        {
          title: "Ajoute-la comme connecteur dans ton IA",
          body: "ChatGPT, Claude, Cursor et Claude Code ont chacun un endroit pour ajouter un connecteur MCP par URL.",
        },
        {
          title: "Connecte-toi (OAuth)",
          body: "Ton IA ouvre la page de connexion Gridar, tu autorises, et c'est branche. Sinon, colle ton jeton btb_ depuis ton tableau de bord.",
        },
        {
          title: "Demande un audit",
          body: '"Audite mondomaine.com et donne-moi les 3 choses a corriger en premier." Ton IA appelle Gridar et te repond avec de vraies donnees.',
        },
      ]}
      mockup={{
        client: "ChatGPT",
        prompt: "Audite demo-entreprise.ca et donne-moi les 3 priorités.",
        tool: "site_seo_score",
      }}
      related={[
        { href: "/gridar-pour-chatgpt", label: "ChatGPT" },
        { href: "/gridar-pour-claude", label: "Claude" },
        { href: "/gridar-pour-agent", label: "Agents & devs" },
      ]}
    />
  );
}
