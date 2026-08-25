import type { Metadata } from "next";
import { ConnectorPage } from "@/components/ConnectorPage";

export const metadata: Metadata = {
  title: "Gridar pour ChatGPT - ton SEO directement dans ChatGPT",
  description:
    "Ajoute Gridar comme connecteur MCP dans ChatGPT : audite ton site, suis tes positions Google et trouve tes mots-cles sans quitter la conversation. URL : mcp.gridar.app/mcp, connexion OAuth.",
  alternates: { canonical: "/gridar-pour-chatgpt" },
  openGraph: {
    title: "Gridar pour ChatGPT",
    description:
      "Branche les outils SEO de Gridar dans ChatGPT via le connecteur MCP. Audit, positions Google, mots-cles, visibilite IA.",
    url: "https://www.gridar.app/gridar-pour-chatgpt",
    type: "website",
  },
};

export default function GridarPourChatgptPage() {
  return (
    <ConnectorPage
      eyebrow="Gridar pour ChatGPT"
      title="Ton SEO, directement dans ChatGPT"
      subtitle="Ajoute Gridar comme connecteur dans ChatGPT. Demande un audit, tes positions Google ou une analyse de concurrents, et ChatGPT te repond avec les vraies donnees de Gridar."
      steps={[
        {
          title: "Ouvre les connecteurs de ChatGPT",
          body: "Reglages -> Connecteurs (ou active le Developer Mode pour les connecteurs custom).",
        },
        {
          title: "Ajoute un connecteur par URL",
          body: "Colle l'URL du serveur MCP de Gridar comme nouveau connecteur.",
          code: "https://mcp.gridar.app/mcp",
        },
        {
          title: "Connecte-toi a Gridar",
          body: "ChatGPT ouvre la page de connexion Gridar (OAuth). Tu autorises, c'est branche.",
        },
        {
          title: "Parle a Gridar dans ChatGPT",
          body: '"Audite mondomaine.com", "Sur quels mots-cles mes concurrents me battent?", "Est-ce que l\'IA de Google me recommande?"',
        },
      ]}
      note="Les connecteurs custom demandent un compte ChatGPT Pro, Team ou Enterprise, ou le Developer Mode active."
      related={[
        { href: "/mcp", label: "Vue d'ensemble MCP" },
        { href: "/gridar-pour-claude", label: "Claude" },
        { href: "/gridar-pour-agent", label: "Agents & devs" },
      ]}
    />
  );
}
