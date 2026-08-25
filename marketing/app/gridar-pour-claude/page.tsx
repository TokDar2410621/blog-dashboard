import type { Metadata } from "next";
import { ConnectorPage } from "@/components/ConnectorPage";

export const metadata: Metadata = {
  title: "Gridar pour Claude - le SEO dans Claude et Claude Desktop",
  description:
    "Branche Gridar dans Claude (claude.ai) et Claude Desktop via le connecteur MCP : audit SEO, positions Google, mots-cles, visibilite IA. URL : mcp.gridar.app/mcp, connexion OAuth.",
  alternates: { canonical: "/gridar-pour-claude" },
  openGraph: {
    title: "Gridar pour Claude",
    description:
      "Les outils SEO de Gridar dans Claude et Claude Desktop, via le connecteur MCP distant.",
    url: "https://www.gridar.app/gridar-pour-claude",
    type: "website",
  },
};

export default function GridarPourClaudePage() {
  return (
    <ConnectorPage
      eyebrow="Gridar pour Claude"
      title="Le SEO de Gridar, dans Claude"
      subtitle="Ajoute Gridar comme connecteur dans Claude (claude.ai) ou Claude Desktop. Claude audite ton site, lit tes positions Google et trouve tes mots-cles, avec de vraies donnees."
      steps={[
        {
          title: "Sur claude.ai : Reglages -> Connecteurs",
          body: "Ajoute un connecteur personnalise avec l'URL du serveur MCP de Gridar.",
          code: "https://mcp.gridar.app/mcp",
        },
        {
          title: "Connecte-toi a Gridar (OAuth)",
          body: "Claude ouvre la page de connexion Gridar, tu autorises, c'est branche.",
        },
        {
          title: "Sur Claude Desktop (option)",
          body: "Ajoute ceci dans ta config, Claude Desktop se branche au serveur distant via le pont mcp-remote :",
          code: `{
  "mcpServers": {
    "gridar": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.gridar.app/mcp"]
    }
  }
}`,
        },
        {
          title: "Demande a Claude",
          body: '"Audite mondomaine.com et priorise les corrections", "Compare mon site a mon concurrent principal".',
        },
      ]}
      mockup={{
        client: "Claude",
        prompt: "Audite demo-entreprise.ca et donne-moi les 3 priorités.",
        tool: "site_seo_score",
      }}
      related={[
        { href: "/mcp", label: "Vue d'ensemble MCP" },
        { href: "/gridar-pour-chatgpt", label: "ChatGPT" },
        { href: "/gridar-pour-agent", label: "Agents & devs" },
      ]}
    />
  );
}
