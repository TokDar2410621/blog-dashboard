import { Search, TrendingUp, Eye, Users, Layers, Zap } from "lucide-react";
import type { ConnectorFeature } from "@/components/ConnectorPage";

/** Capacites exposees par le serveur MCP de Gridar, partagees par les pages connecteur. */
export const CONNECTOR_FEATURES: ConnectorFeature[] = [
  {
    icon: Search,
    title: "Auditer un site",
    desc: "Score SEO complet, vitesse mobile, balises, contenu manquant, en 30 secondes.",
  },
  {
    icon: TrendingUp,
    title: "Suivre les positions Google",
    desc: "Ou tu ranques sur Google.ca, geolocalise au Quebec, par mot-cle.",
  },
  {
    icon: Eye,
    title: "Mesurer la visibilite IA",
    desc: "Savoir si l'IA de Google recommande une entreprise ou ses concurrents.",
  },
  {
    icon: Users,
    title: "Analyser les concurrents",
    desc: "Les mots-cles ou les concurrents rankent, les ecarts a combler.",
  },
  {
    icon: Layers,
    title: "Batir des clusters de contenu",
    desc: "Cartographier les sujets et le maillage interne d'un site.",
  },
  {
    icon: Zap,
    title: "Indexer plus vite",
    desc: "Soumettre les pages via IndexNow et suivre la couverture Search Console.",
  },
];
