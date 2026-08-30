import type { Metadata } from "next";
import Link from "next/link";
import { AlertTriangle, GitBranch, Link2, Network, Route, Scissors } from "lucide-react";

import { SeoLanding, type Benefit, type FaqItem } from "@/components/SeoLanding";

const PAGE_URL = "https://www.gridar.app/maillage-interne-automatique";

// Cible mesurée le 2026-08-30. Search Console sur 180 jours :
// "maillage interne automatique" pèse 62 impressions en position moyenne 58,
// sans page dédiée. SERP réel : central.yourtext.guru, learnthings.fr,
// seomix.fr, agencelaboite.com, inlinks.com. gridar.app en est absent.
export const metadata: Metadata = {
  title: { absolute: "Maillage interne automatique : où ça marche, où ça casse | Gridar" },
  description:
    "Le maillage interne automatique fait gagner des heures et peut abîmer un site. La ligne exacte, les erreurs classiques, et comment obtenir des suggestions mesurées.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "Maillage interne automatique : où ça marche, où ça casse",
    description:
      "Ancres identiques, liens qui n'aident personne, pages orphelines oubliées : ce qu'une automatisation du maillage doit éviter.",
    url: PAGE_URL,
    type: "website",
    siteName: "Gridar",
    locale: "fr_CA",
  },
  robots: { index: true, follow: true },
};

const FAQ: FaqItem[] = [
  {
    question: "C'est quoi le maillage interne ?",
    answer:
      "C'est l'ensemble des liens qui vont d'une page de votre site vers une autre page du même site. Ils servent à deux choses en même temps : guider un lecteur vers la suite logique de sa lecture, et faire circuler l'autorité entre vos pages. Une page vers laquelle rien ne pointe est presque invisible, quelle que soit sa qualité, parce que ni le lecteur ni le robot n'ont de chemin pour l'atteindre.",
  },
  {
    question: "Le maillage interne peut-il vraiment être automatisé ?",
    answer:
      "La détection oui, la pose demande une validation. Une machine repère très bien les pages orphelines, les liens morts et les paires de pages qui parlent du même sujet sans se lier. Elle juge mal si un lien sert vraiment le lecteur à cet endroit du texte. Les outils qui insèrent automatiquement des liens sur simple correspondance de mots-clés produisent des phrases où le lien tombe à côté du propos.",
  },
  {
    question: "Combien de liens internes par page ?",
    answer:
      "Il n'y a pas de nombre magique, et se fixer un quota est la meilleure façon de produire des liens inutiles. Le critère utile est l'utilité : chaque lien doit répondre à une question que le lecteur se pose à cet endroit précis. En pratique, un article de fond en porte naturellement entre trois et dix vers d'autres pages du site, et une page qui n'en porte aucun est un signal qu'il manque du contexte.",
  },
  {
    question: "Faut-il varier les textes d'ancre ?",
    answer:
      "Oui, et c'est le premier défaut des automatisations naïves. Cent liens portant exactement la même ancre vers la même page ressemblent à un schéma généré, pas à un site rédigé. Écrivez l'ancre en fonction de la phrase qui l'entoure : elle doit décrire ce que le lecteur va trouver, ce qui produit naturellement de la variation.",
  },
  {
    question: "Comment repérer les pages orphelines ?",
    answer:
      "En comparant la liste des pages de votre sitemap à la liste des pages réellement atteignables par un lien interne. Tout ce qui apparaît dans la première et pas dans la seconde est orphelin. C'est une opération purement mécanique, donc entièrement automatisable, et c'est souvent là que se cachent des pages de service qui avaient coûté cher à produire.",
  },
  {
    question: "Un lien interne peut-il nuire ?",
    answer:
      "Oui, dans trois cas. Un lien vers une page en erreur gaspille le passage du robot et frustre le lecteur. Un lien massif vers une page peu importante détourne l'attention de vos pages qui convertissent. Et un lien inséré au milieu d'une phrase qu'il ne concerne pas dégrade la lecture, ce qui finit par se voir dans le comportement des visiteurs.",
  },
];

const BENEFITS: Benefit[] = [
  {
    icon: Network,
    title: "Le graphe réel de vos pages",
    text: "Qui pointe vers qui, avec les grappes et les points isolés visibles d'un coup d'oeil au lieu d'un tableur.",
  },
  {
    icon: Route,
    title: "Les pages orphelines nommées",
    text: "Les pages qu'aucun lien interne n'atteint, comparées au sitemap. Purement mécanique, donc fiable.",
  },
  {
    icon: Link2,
    title: "Des paires proposées, pas imposées",
    text: "Les liens manquants sont calculés sur le contenu réel des deux pages, et vous décidez lesquels posez.",
  },
  {
    icon: Scissors,
    title: "Les liens morts d'abord",
    text: "Un lien vers une page en erreur coûte deux fois : il gaspille le passage du robot et il frustre le lecteur.",
  },
  {
    icon: AlertTriangle,
    title: "Aucune insertion en aveugle",
    text: "Rien n'est écrit dans vos textes sans votre accord. Un lien posé au mauvais endroit se remarque plus qu'il ne rapporte.",
  },
  {
    icon: GitBranch,
    title: "Pensé par grappe",
    text: "Les liens qui comptent le plus relient les pages d'un même thème, là où l'autorité se concentre au lieu de se diluer.",
  },
];

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Analyse et suggestions de maillage interne",
  serviceType: "Optimisation du maillage interne SEO",
  description:
    "Cartographie du maillage interne d'un site, détection des pages orphelines et des liens morts, et suggestions de liens manquants calculées sur le contenu réel des pages.",
  url: PAGE_URL,
  provider: { "@type": "Organization", name: "Gridar", url: "https://www.gridar.app" },
  areaServed: { "@type": "AdministrativeArea", name: "Québec, Canada" },
};

export default function MaillageInterneAutomatiquePage() {
  return (
    <SeoLanding
      trail="Maillage interne"
      badge="Audit gratuit, sans inscription"
      badgeIcon={Network}
      h1="Maillage interne automatique : ce qui s'automatise et ce qui casse"
      lede="Détecter les pages orphelines et les liens morts est mécanique, donc automatisable sans risque. Insérer des liens dans vos textes ne l'est pas. Voici la ligne, et pourquoi elle compte."
      ctaPrimary={{ href: "/audit", label: "Cartographier mes liens" }}
      ctaSecondary={{ href: "/tools", label: "Voir les outils gratuits" }}
      benefitsTitle="Ce qu'une bonne automatisation du maillage fait"
      benefits={BENEFITS}
      faqTitle="Questions fréquentes sur le maillage interne automatique"
      faq={FAQ}
      finalCtaTitle="Commencez par voir votre graphe"
      finalCtaText="L'audit gratuit explore votre site, relève les liens morts et vous montre ce qui n'est atteignable par aucun lien interne. Sans inscription, et le rapport se partage par lien."
      finalCtaPrimary={{ href: "/audit", label: "Auditer mon maillage gratuitement" }}
      finalCtaSecondary={{ href: "/login", label: "Ouvrir un compte" }}
      jsonLd={serviceJsonLd}
    >
      <h2>Pourquoi le maillage interne pèse plus qu&apos;on ne croit</h2>
      <p>
        Un lien interne fait deux choses en même temps, et on n&apos;en retient
        généralement qu&apos;une. La première est humaine : il propose au lecteur la suite
        logique de sa lecture, au moment où il se pose la question. La seconde est
        structurelle : il fait circuler l&apos;autorité d&apos;une page vers une autre, et
        il donne au robot un chemin pour découvrir vos pages.
      </p>
      <p>
        C&apos;est pour ça qu&apos;une page vers laquelle rien ne pointe reste presque
        invisible, même bien écrite. Elle existe dans le sitemap, elle est peut-être même
        indexée, mais rien ne la recommande à l&apos;intérieur de votre propre site. Le
        cas le plus courant est la page de service produite pour une campagne, publiée, et
        jamais reliée au reste.
      </p>

      <h2>Ce qui s&apos;automatise sans aucun risque</h2>
      <p>
        <strong>Les pages orphelines.</strong> Comparer la liste des pages du sitemap à la
        liste des pages atteignables par un lien interne est une opération purement
        mécanique. La différence donne les orphelines, sans jugement ni interprétation.
        C&apos;est souvent la découverte la plus rentable d&apos;un premier audit.
      </p>
      <p>
        <strong>Les liens morts.</strong> Un lien qui pointe vers une page en erreur coûte
        deux fois : il gaspille le passage du robot et il envoie un lecteur dans le vide.
        Les détecter demande de suivre chaque lien et de lire le code de réponse ; aucune
        décision humaine n&apos;entre en jeu.
      </p>
      <p>
        <strong>Le graphe des liens.</strong> Voir qui pointe vers qui révèle en un coup
        d&apos;oeil les grappes bien reliées, les pages isolées et les pages qui reçoivent
        tous les liens sans en émettre. Un tableur ne donne jamais cette lecture.
      </p>
      <p>
        <strong>Les paires manquantes.</strong> Deux pages qui traitent d&apos;un sujet
        proche sans se lier sont détectables en comparant leur contenu réel. La proposition
        est automatique ; la décision de poser le lien, non, et c&apos;est là que commence
        la deuxième partie.
      </p>

      <h2>Ce qui casse quand on automatise l&apos;insertion</h2>
      <p>
        Les outils qui insèrent automatiquement des liens dans vos textes travaillent
        presque tous par correspondance de mots-clés : ils cherchent une expression dans
        une page et la transforment en lien. Le résultat est prévisible et se reconnaît
        immédiatement à la lecture.
      </p>
      <p>
        <strong>Des ancres toutes identiques.</strong> Cent liens portant exactement la
        même expression vers la même page ne ressemblent pas à un site rédigé, mais à un
        schéma généré. Une ancre doit décrire ce que le lecteur va trouver, dans les mots
        de la phrase qui l&apos;entoure, ce qui produit naturellement de la variation.
      </p>
      <p>
        <strong>Des liens qui tombent à côté.</strong> L&apos;expression apparaît dans une
        phrase qui parle d&apos;autre chose, et le lien y est posé quand même. Le lecteur
        clique, arrive sur une page sans rapport avec sa question, et repart. Ce
        comportement finit par se voir.
      </p>
      <p>
        <strong>Une dilution du budget d&apos;attention.</strong> Ajouter des liens partout
        ne renforce rien : cela répartit l&apos;autorité sur davantage de destinations. Un
        maillage utile concentre les liens vers les pages qui convertissent, pas vers
        toutes les pages également.
      </p>

      <h2>La méthode qui garde les deux avantages</h2>
      <p>
        Laissez la machine faire l&apos;inventaire et gardez la décision. Concrètement :
        l&apos;outil explore, dresse le graphe, nomme les orphelines, liste les liens
        morts et propose les paires manquantes avec la raison du rapprochement. Vous
        parcourez la liste et vous validez, ce qui prend quelques minutes pour un travail
        qui prenait une journée à la main.
      </p>
      <p>
        Le tri se fait par grappe. Les liens qui rapportent le plus relient des pages du
        même thème, parce que c&apos;est là que l&apos;autorité se concentre au lieu de se
        diluer. Un lien entre deux pages sans rapport ne fait de mal à personne, mais il ne
        fait rien non plus.
      </p>
      <p>
        Dernier point souvent oublié : le maillage se refait après chaque publication.
        Chaque nouvel article devrait recevoir des liens depuis les pages existantes, pas
        seulement en émettre. C&apos;est la moitié du travail que presque tout le monde
        saute, et celle qui décide si un article neuf est découvert ou reste au fond du
        site.
      </p>

      <h2>Par où commencer</h2>
      <p>
        L&apos;<Link href="/audit">audit gratuit</Link> explore le site, relève les liens
        morts et signale ce qui n&apos;est atteignable par aucun lien interne, sans
        inscription. C&apos;est le point de départ, parce qu&apos;il n&apos;y a aucun
        intérêt à ajouter des liens tant que ceux qui existent pointent vers des pages en
        erreur.
      </p>
      <p>
        Ensuite, le maillage se planifie avec le contenu : les liens à poser dépendent des
        pages que vous allez écrire. La page{" "}
        <Link href="/calendrier-editorial-seo">calendrier éditorial SEO</Link> décrit
        comment construire cette file à partir de mesures, et le{" "}
        <Link href="/suivi-position-google-canada">suivi de position</Link> permet de
        vérifier si les liens posés ont bougé quelque chose, ville par ville.
      </p>
    </SeoLanding>
  );
}
