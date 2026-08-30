import type { Metadata } from "next";
import Link from "next/link";
import { Bot, Gauge, LineChart, Link2, Radar, ShieldCheck } from "lucide-react";

import { SeoLanding, type Benefit, type FaqItem } from "@/components/SeoLanding";

const PAGE_URL = "https://www.gridar.app/logiciel-referencement-automatique";

// Cible mesurée le 2026-08-30. Search Console sur 180 jours : le groupe
// "logiciel de référencement" pèse environ 330 impressions réparties sur neuf
// variantes (logiciel de référencement automatique, outils de référencement
// automatique, logiciel référencement, logiciel de référencement naturel,
// logiciel suivi de positionnement...), toutes entre la position 43 et 87.
// SERP réel : getapp.ca, capterra.ca, bluehost.com, referencement-google-gratuit.com.
// Aucune page du site ne traitait ce groupe. gridar.app en est absent.
export const metadata: Metadata = {
  title: { absolute: "Logiciel de référencement automatique | Gridar" },
  description:
    "Ce qu'un logiciel de référencement automatise vraiment, et ce qu'il ne devrait jamais automatiser. Audit, suivi, opportunités et rédaction, mesurés au Québec.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "Logiciel de référencement automatique : ce qui s'automatise vraiment",
    description:
      "Audit technique, suivi de positions, détection d'opportunités et rédaction assistée. Ce qui se pilote tout seul et ce qui demande votre décision.",
    url: PAGE_URL,
    type: "website",
    siteName: "Gridar",
    locale: "fr_CA",
  },
  robots: { index: true, follow: true },
};

const FAQ: FaqItem[] = [
  {
    question: "Qu'est-ce qu'un logiciel de référencement automatique ?",
    answer:
      "C'est un outil qui exécute sans intervention les tâches SEO répétitives et mesurables : explorer un site, relever les erreurs techniques, interroger les pages de résultats pour connaître vos positions, repérer les pages qui perdent du trafic, proposer des liens internes. Ce qui ne s'automatise pas sans risque, c'est la décision : quelle page mérite votre temps, quel angle adopter, quel contenu publier. Un logiciel qui prétend automatiser aussi cette partie automatise surtout la production de pages inutiles.",
  },
  {
    question: "Un logiciel peut-il rédiger et publier mes articles tout seul ?",
    answer:
      "Techniquement oui, et c'est exactement là qu'il faut être prudent. Gridar génère des articles à partir de vos mots-clés suivis et de la mémoire de votre site, mais le mode par défaut les dépose en brouillon pour relecture. Publier sans relecture reste possible et reste votre choix, pas le nôtre. Un texte non relu qui se trompe sur vos prix ou vos services coûte plus cher que les heures qu'il fait gagner.",
  },
  {
    question: "Quelle différence avec Semrush ou Ahrefs ?",
    answer:
      "Ces plateformes sont d'excellents outils d'analyse conçus pour un marché international : elles mesurent très bien et vous laissent tout le travail d'exécution. Gridar est bâti dans l'autre sens, autour du Québec et de l'exécution : les positions sont relevées sur Google.ca en français, et l'outil va jusqu'à produire les pages et les liens internes. Les deux approches ne s'excluent pas, elles ne répondent simplement pas à la même question.",
  },
  {
    question: "Faut-il des compétences techniques pour l'utiliser ?",
    answer:
      "Non pour l'audit et les outils publics : une adresse web suffit, sans inscription. Oui pour tirer le maximum du reste, parce que corriger une balise, poser une redirection ou brancher Search Console demande d'avoir accès au site. Si vous n'avez pas cet accès, l'outil vous dira quoi demander à la personne qui l'a, avec le détail exact.",
  },
  {
    question: "Le logiciel fonctionne-t-il si mon site n'est pas hébergé chez vous ?",
    answer:
      "L'analyse fonctionne sur n'importe quel site accessible publiquement : audit technique, positions, concurrents, visibilité dans les réponses des IA. La livraison automatique du contenu, elle, dépend de votre plateforme : quand le CMS n'est pas connecté, l'article est produit et vous reste à publier. C'est une limite réelle et il vaut mieux la connaître avant de s'abonner qu'après.",
  },
  {
    question: "Comment savoir si l'automatisation a servi à quelque chose ?",
    answer:
      "En comparant des mesures prises avant et après, pas des promesses. Chaque chiffre affiché dans Gridar vient d'une mesure datée : une page de résultats réellement interrogée, une exploration réellement effectuée, une réponse d'IA réellement obtenue. Quand une donnée manque, l'outil le dit au lieu d'afficher zéro, parce qu'un zéro inventé fausse toutes les décisions qui suivent.",
  },
];

const BENEFITS: Benefit[] = [
  {
    icon: Gauge,
    title: "Audit technique sans inscription",
    text: "Une adresse web suffit pour obtenir l'exploration, les erreurs techniques et les priorités de correction, gratuitement.",
  },
  {
    icon: LineChart,
    title: "Positions relevées sur Google.ca",
    text: "Le rang mesuré est celui d'un client québécois qui cherche en français, pas une moyenne mondiale sur google.com.",
  },
  {
    icon: Radar,
    title: "Opportunités classées, pas listées",
    text: "Les mots-clés où vos concurrents sont présents et vous absents, avec la preuve : la page de résultats qui le montre.",
  },
  {
    icon: Link2,
    title: "Maillage interne proposé",
    text: "Les liens qui manquent entre vos pages existantes, calculés sur leur contenu réel plutôt que sur une règle générique.",
  },
  {
    icon: Bot,
    title: "Pilotable par un agent IA",
    text: "Un connecteur MCP expose les mêmes fonctions à ChatGPT ou Claude, pour déclencher un audit ou une génération depuis une conversation.",
  },
  {
    icon: ShieldCheck,
    title: "Aucun chiffre inventé",
    text: "Quand une mesure échoue, l'outil affiche la raison au lieu d'un zéro. Un zéro inventé fausse toutes les décisions suivantes.",
  },
];

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Gridar",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Navigateur web",
  url: PAGE_URL,
  description:
    "Logiciel de référencement qui automatise l'audit technique, le suivi des positions sur Google.ca, la détection d'opportunités, le maillage interne et la rédaction assistée, pour les PME du Québec.",
  inLanguage: "fr-CA",
  provider: { "@type": "Organization", name: "Gridar", url: "https://www.gridar.app" },
  featureList: [
    "Audit technique de site",
    "Suivi de positions sur Google.ca géolocalisé",
    "Détection d'opportunités face aux concurrents",
    "Suggestions de maillage interne",
    "Génération d'articles à partir des mots-clés suivis",
    "Mesure de la visibilité dans les réponses des IA",
  ],
};

export default function LogicielReferencementAutomatiquePage() {
  return (
    <SeoLanding
      trail="Logiciel de référencement"
      badge="Audit gratuit, sans inscription"
      badgeIcon={Bot}
      h1="Logiciel de référencement automatique : ce qui s'automatise vraiment"
      lede="Un logiciel SEO peut explorer, mesurer et proposer sans vous. Il ne devrait jamais décider à votre place. Voici la ligne exacte, et ce que Gridar fait de chaque côté."
      ctaPrimary={{ href: "/audit", label: "Lancer un audit gratuit" }}
      ctaSecondary={{ href: "/tools", label: "Voir les outils gratuits" }}
      benefitsTitle="Ce que le logiciel exécute sans vous"
      benefits={BENEFITS}
      faqTitle="Questions fréquentes sur les logiciels de référencement automatique"
      faq={FAQ}
      finalCtaTitle="Commencez par une mesure, pas par un abonnement"
      finalCtaText="L'audit technique est gratuit et ne demande aucune inscription. Vous saurez ce que votre site a réellement, avant de décider si un logiciel vaut la dépense."
      finalCtaPrimary={{ href: "/audit", label: "Auditer mon site gratuitement" }}
      finalCtaSecondary={{ href: "/login", label: "Ouvrir un compte" }}
      jsonLd={serviceJsonLd}
    >
      <h2>La frontière entre automatiser et déléguer</h2>
      <p>
        Toutes les tâches SEO ne se valent pas devant l&apos;automatisation. Certaines sont
        répétitives, mesurables et sans jugement : explorer un site, vérifier qu&apos;une
        page répond bien, relever un rang dans une page de résultats, comparer les liens
        internes de deux pages. Une machine les fait mieux qu&apos;un humain, plus souvent,
        et sans se lasser.
      </p>
      <p>
        D&apos;autres reposent entièrement sur du jugement : décider quel client vous voulez
        attirer, quel angle vous distingue, ce que vous refusez de vendre. Aucun logiciel
        ne connaît ces réponses, et ceux qui prétendent les deviner produisent des pages
        interchangeables que Google traite exactement comme telles.
      </p>
      <p>
        Un bon logiciel de référencement automatique se juge donc à l&apos;endroit où il
        place cette frontière. Celui qui automatise la mesure et vous rend la décision
        vous fait gagner du temps. Celui qui automatise aussi la décision vous fait gagner
        du volume, ce qui n&apos;est pas la même chose et coûte souvent plus cher.
      </p>

      <h2>Ce que Gridar exécute sans intervention</h2>
      <p>
        <strong>L&apos;audit technique.</strong> Une adresse web suffit : l&apos;
        <Link href="/audit">audit gratuit</Link> explore le site, relève ce qui bloque
        l&apos;indexation, les titres et descriptions hors bornes, les liens morts, les
        problèmes de rendu. Aucune inscription, et le rapport est partageable par lien.
      </p>
      <p>
        <strong>Le relevé des positions.</strong> Les rangs sont mesurés sur Google.ca, en
        français, avec une géolocalisation à l&apos;échelle de la ville. C&apos;est ce qui
        sépare une donnée utile au Québec d&apos;une moyenne internationale. Le{" "}
        <Link href="/suivi-position-google-canada">vérificateur de position</Link> fait le
        contrôle ponctuel gratuitement.
      </p>
      <p>
        <strong>La détection d&apos;opportunités.</strong> L&apos;outil interroge de vraies
        pages de résultats pour trouver les requêtes où vos concurrents apparaissent et
        vous non. Chaque opportunité arrive avec sa preuve : la liste des domaines qui
        occupent le SERP. Le{" "}
        <Link href="/tools/competitor-gap">détecteur d&apos;écarts</Link> en donne un
        aperçu sans compte.
      </p>
      <p>
        <strong>La surveillance de l&apos;érosion.</strong> Une page qui perdait du trafic
        se remarquait autrefois six mois trop tard. La comparaison des impressions dans le
        temps signale la baisse pendant qu&apos;elle est encore réparable, ce qui est le
        seul moment où la réparation coûte moins que la réécriture.
      </p>

      <h2>Ce qui demande votre décision, et pourquoi</h2>
      <p>
        La rédaction est le cas le plus clair. Gridar génère des articles à partir de vos
        mots-clés suivis et de la mémoire de votre site, mais le mode par défaut les dépose
        en brouillon. Ce choix n&apos;est pas une limite technique : publier sans relecture
        fonctionne. C&apos;est une limite de prudence, parce qu&apos;un texte qui se trompe
        sur vos prix, vos délais ou vos zones desservies vous coûte plus que les heures
        qu&apos;il fait gagner.
      </p>
      <p>
        Le maillage interne suit la même logique. L&apos;outil propose les liens qui
        manquent entre vos pages, calculés sur leur contenu réel. Il vous laisse valider,
        parce qu&apos;un lien pertinent pour un algorithme peut être absurde pour un
        lecteur, et que le lecteur est celui qui achète.
      </p>
      <p>
        Enfin, les corrections techniques qui touchent le site lui-même restent des actions
        que vous déclenchez. Une redirection posée automatiquement au mauvais endroit fait
        disparaître une page qui fonctionnait. L&apos;outil prépare, documente, et attend.
      </p>

      <h2>Automatique ne veut pas dire aveugle</h2>
      <p>
        Le vrai risque d&apos;un logiciel de référencement automatique n&apos;est pas
        qu&apos;il en fasse trop, c&apos;est qu&apos;il affiche des chiffres que personne
        n&apos;a mesurés. Un score inventé, une estimation de volume présentée comme une
        donnée, un zéro affiché parce qu&apos;une requête a échoué : chacune de ces valeurs
        oriente une décision et aucune ne repose sur rien.
      </p>
      <p>
        Gridar applique la règle inverse. Chaque nombre affiché correspond à une mesure
        datée, et quand la mesure échoue, l&apos;outil affiche la raison plutôt qu&apos;un
        zéro. C&apos;est moins flatteur sur une capture d&apos;écran, et c&apos;est la
        seule façon de garder un tableau de bord sur lequel on peut décider.
      </p>

      <h2>Faire tourner le logiciel depuis un agent IA</h2>
      <p>
        Les mêmes fonctions sont exposées par un connecteur MCP, ce qui permet à ChatGPT ou
        à Claude de déclencher un audit, de lire vos positions ou de générer un article
        depuis une conversation. C&apos;est la forme d&apos;automatisation la plus utile
        aujourd&apos;hui : vous décrivez l&apos;intention en français, l&apos;agent appelle
        les bons outils, et vous gardez la main sur ce qui est publié. Le détail du
        branchement est sur la page <Link href="/mcp">connecteur MCP</Link>.
      </p>
      <p>
        Pour un premier contact, restez sur la mesure : l&apos;
        <Link href="/audit">audit gratuit</Link> ne demande ni courriel ni carte, et vous
        saurez en quelques minutes si le problème de votre site est technique, éditorial ou
        concurrentiel. Les trois ne se règlent pas avec le même outil.
      </p>
    </SeoLanding>
  );
}
