import type { Metadata } from "next";
import { ConnectorPage } from "@/components/ConnectorPage";
import { CONNECTOR_FEATURES } from "@/components/connector-features";

export const metadata: Metadata = {
  title: "Gridar pour tes agents - l'API SEO en MCP (Cursor, Claude Code)",
  description:
    "Donne a tes agents les outils SEO de Gridar via MCP : audit, positions Google, clusters, indexation. Branche-le dans Cursor, Claude Code ou ton propre agent. URL : mcp.gridar.app/mcp.",
  alternates: { canonical: "/gridar-pour-agent" },
  openGraph: {
    title: "Gridar pour tes agents",
    description:
      "Le serveur MCP de Gridar pour Cursor, Claude Code et tes agents. Audit, positions, clusters, indexation.",
    url: "https://www.gridar.app/gridar-pour-agent",
    type: "website",
  },
};

export default function GridarPourAgentPage() {
  return (
    <ConnectorPage
      eyebrow="Gridar pour agents & devs"
      title="Le SEO de Gridar dans tes agents"
      subtitle="Gridar est un serveur MCP distant standard. Branche-le dans Cursor, Claude Code ou ton propre agent, et automatise audits, suivi de positions, clusters et indexation."
      steps={[
        {
          title: "Claude Code",
          body: "Une commande, et Gridar est disponible dans tes sessions :",
          code: "claude mcp add --transport http gridar https://mcp.gridar.app/mcp",
        },
        {
          title: "Cursor",
          body: "Reglages -> MCP -> Add server. Ajoute un serveur de type URL :",
          code: "https://mcp.gridar.app/mcp",
        },
        {
          title: "Authentification",
          body: "OAuth automatique au premier appel, ou passe ton jeton en en-tete pour un agent headless :",
          code: "Authorization: Bearer btb_ton_token",
        },
        {
          title: "Ton propre agent",
          body: "N'importe quel client MCP (SDK OpenAI, Anthropic, LangChain...) lit la decouverte OAuth du serveur et se branche. Le serveur suit le standard MCP (Streamable HTTP + OAuth 2.1).",
        },
      ]}
      features={CONNECTOR_FEATURES}
      related={[
        { href: "/mcp", label: "Vue d'ensemble MCP" },
        { href: "/gridar-pour-chatgpt", label: "ChatGPT" },
        { href: "/gridar-pour-claude", label: "Claude" },
      ]}
    />
  );
}
