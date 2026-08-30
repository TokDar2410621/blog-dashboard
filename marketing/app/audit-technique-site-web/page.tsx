import type { Metadata } from "next";
import Link from "next/link";
import { Bug, FileSearch, Gauge, Link2, Repeat, Search } from "lucide-react";

import { SeoLanding, type Benefit, type FaqItem } from "@/components/SeoLanding";

const PAGE_URL = "https://www.gridar.app/audit-technique-site-web";

// Cible mesurée le 2026-08-30 par la pipeline de découverte : Google suggère
// "audit technique site web" et trois variantes, le SERP est commercial et
// gridar.app en est absent. Occupé par digitad.ca, seoptimer.com, eskimoz.fr,
// evolvingweb.com et seranking.com.
//
// Ne cannibalise pas /audit : les SERP de "audit seo gratuit" et de "audit
// technique site web" ne partagent qu'un résultat sur dix. Deux intentions.
export const metadata: Metadata = {
  title: { absolute: "Audit technique site web : ce qu'il révèle | Gridar" },
  description:
    "Un audit technique regarde ce que Google voit, pas ce que vous voyez. Indexation, rendu, redirections, liens morts : ce qu'il révèle et dans quel ordre corriger.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "Audit technique site web : ce qu'il révèle et dans quel ordre corriger",
    description:
      "Indexation bloquée, rendu dépendant du JavaScript, redirections en chaîne, liens morts. Les problèmes qui annulent tout le reste.",
    url: PAGE_URL,
    type: "website",
    siteName: "Gridar",
    locale: "fr_CA",
  },
  robots: { index: true, follow: true },
};

const FAQ: FaqItem[] = [
  {
    question: "C'est quoi un audit technique de site web ?",
    answer:
      "C'est l'examen de tout ce qui, dans la construction du site, empêche un moteur de le lire, de le comprendre ou de le classer. On ne juge pas le contenu ni le design : on vérifie que les pages répondent, qu'elles sont indexables, que le contenu existe sans exécuter de JavaScript, que les redirections ne partent pas en chaîne et que les liens internes pointent quelque part. C'est la couche en dessous du référencement, celle qui décide si le reste sert à quelque chose.",
  },
  {
    question: "Quelle différence avec un audit SEO ?",
    answer:
      "L'audit SEO couvre aussi les mots-clés, le contenu, la concurrence et les liens externes. L'audit technique se limite à ce que la machine voit. La distinction compte parce que l'ordre des travaux en dépend : tant qu'une page est bloquée à l'indexation, améliorer son texte ne produit rien. On règle la technique d'abord parce qu'elle est la moins chère et qu'elle conditionne tout le reste.",
  },
  {
    question: "Que faut-il corriger en premier ?",
    answer:
      "Dans cet ordre : ce qui empêche l'indexation, ce qui empêche le rendu, ce qui casse la navigation, puis le reste. Une page en noindex par erreur coûte la page entière. Un contenu qui n'apparaît qu'après exécution du JavaScript coûte une partie du texte. Une balise de titre trop longue coûte quelques clics. Un rapport qui liste ces trois problèmes sur le même plan vous fait perdre du temps.",
  },
  {
    question: "À quelle fréquence refaire l'audit technique ?",
    answer:
      "Après chaque changement structurel, et au moins deux fois par an. Une refonte, une migration, un changement de thème ou l'ajout d'un module introduisent des régressions invisibles depuis le navigateur : une redirection perdue, un fichier robots.txt écrasé, une balise canonique qui pointe ailleurs. Ces régressions ne se voient pas à l'oeil et se paient en trafic quelques semaines plus tard.",
  },
  {
    question: "Faut-il un développeur pour appliquer les corrections ?",
    answer:
      "Pour une partie, oui, parce que corriger une redirection ou une balise demande un accès au site ou à son CMS. Le rôle de l'audit est de rendre cette demande précise : quelle page, quel problème, quelle correction attendue. Une demande formulée ainsi coûte quelques minutes à un développeur, là où « le SEO ne marche pas » coûte une réunion.",
  },
  {
    question: "L'audit est-il vraiment gratuit ?",
    answer:
      "Oui, sans inscription ni carte. Vous entrez une adresse, l'outil explore le site et rend un rapport daté que vous pouvez partager par lien. Ce qui relève de l'abonnement, c'est la répétition automatique de cet audit dans le temps et le suivi des corrections. Le premier passage, celui qui vous dit si vous avez un problème, ne coûte rien.",
  },
];

const BENEFITS: Benefit[] = [
  {
    icon: Search,
    title: "Ce que Google voit, pas votre navigateur",
    text: "L'exploration lit vos pages comme un robot : sans vos cookies, sans votre session, et sans attendre le JavaScript.",
  },
  {
    icon: Bug,
    title: "L'indexation d'abord",
    text: "Une page en noindex par erreur coûte la page entière. C'est le premier problème cherché, avant tout le reste.",
  },
  {
    icon: Repeat,
    title: "Les redirections en chaîne",
    text: "Trois sauts pour atteindre une page gaspillent le passage du robot et ralentissent le visiteur. Elles se voient rarement à l'oeil.",
  },
  {
    icon: Link2,
    title: "Les liens morts nommés",
    text: "Chaque lien interne est suivi et son code de réponse relevé. Un lien vers une page en erreur coûte deux fois.",
  },
  {
    icon: Gauge,
    title: "Ordonné par conséquence",
    text: "Pas un score sur cent qui mélange une balise trop longue et une page invisible. Une liste courte, la plus coûteuse en tête.",
  },
  {
    icon: FileSearch,
    title: "Un rapport partageable",
    text: "Un lien à jeton que votre développeur ouvre sans compte, avec le détail exact de ce qu'il y a à corriger.",
  },
];

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Audit technique de site web",
  serviceType: "Audit technique SEO",
  description:
    "Exploration d'un site web pour relever ce qui empêche un moteur de le lire : indexation bloquée, rendu dépendant du JavaScript, redirections en chaîne, liens morts et balises hors bornes. Rapport daté et partageable, sans inscription.",
  url: PAGE_URL,
  provider: { "@type": "Organization", name: "Gridar", url: "https://www.gridar.app" },
  areaServed: { "@type": "AdministrativeArea", name: "Québec, Canada" },
  offers: { "@type": "Offer", price: "0", priceCurrency: "CAD" },
};

export default function AuditTechniqueSiteWebPage() {
  return (
    <SeoLanding
      trail="Audit technique"
      badge="Audit gratuit, sans inscription"
      badgeIcon={FileSearch}
      h1="Audit technique site web : ce que Google voit et que vous ne voyez pas"
      lede="Votre site s'affiche parfaitement dans votre navigateur. Ça ne dit rien de ce qu'un moteur en lit. L'audit technique compare les deux, et l'écart est souvent la vraie raison pour laquelle rien ne décolle."
      ctaPrimary={{ href: "/audit", label: "Lancer l'audit gratuit" }}
      ctaSecondary={{ href: "/tools", label: "Voir les outils gratuits" }}
      benefitsTitle="Ce que l'exploration relève"
      benefits={BENEFITS}
      faqTitle="Questions fréquentes sur l'audit technique d'un site web"
      faq={FAQ}
      finalCtaTitle="Une adresse suffit"
      finalCtaText="L'audit explore votre site et rend un rapport daté, partageable par lien, sans inscription ni carte. Vous saurez en quelques minutes si votre problème est technique."
      finalCtaPrimary={{ href: "/audit", label: "Auditer mon site" }}
      finalCtaSecondary={{ href: "/login", label: "Ouvrir un compte" }}
      jsonLd={serviceJsonLd}
    >
      <h2>Pourquoi votre navigateur vous ment</h2>
      <p>
        Vous ouvrez votre site, tout s&apos;affiche, les images chargent, le menu
        fonctionne. Vous en concluez logiquement que le site va bien. Sauf que vous le
        visitez avec votre session, vos cookies, votre connexion rapide et un navigateur
        qui exécute tout le JavaScript avant que vous ne regardiez.
      </p>
      <p>
        Un moteur ne fait rien de tout ça de la même façon. Il arrive sans session, il lit
        d&apos;abord le code source brut, il suit les instructions du fichier robots.txt et
        des balises d&apos;indexation, et il attribue à votre site un budget d&apos;
        exploration limité. Chaque redirection inutile, chaque lien mort, chaque page
        dupliquée consomme ce budget sans rien produire.
      </p>
      <p>
        L&apos;audit technique consiste à regarder le site depuis cette position-là. Le
        résultat surprend souvent : des pages entières invisibles, du contenu qui
        n&apos;existe qu&apos;après exécution du JavaScript, une balise canonique qui
        renvoie tout vers l&apos;accueil depuis une mise à jour de thème.
      </p>

      <h2>Les quatre familles de problèmes, par ordre de coût</h2>
      <p>
        <strong>Un. Ce qui empêche l&apos;indexation.</strong> Une balise noindex laissée
        après une refonte, une règle de blocage trop large dans le robots.txt, une page
        derrière une authentification. Le coût est total : la page n&apos;existe pas pour
        le moteur, quel que soit son contenu. C&apos;est le premier problème à chercher et
        souvent le plus rapide à corriger.
      </p>
      <p>
        <strong>Deux. Ce qui empêche le rendu.</strong> Un contenu injecté par JavaScript
        après le chargement peut être lu, mais avec retard et de façon moins fiable. Sur un
        site dont le texte principal dépend entièrement du rendu côté client, une partie du
        contenu ne pèse rien. Le test est simple : lire le code source brut et chercher son
        propre texte dedans.
      </p>
      <p>
        <strong>Trois. Ce qui casse la navigation.</strong> Redirections en chaîne, boucles,
        liens internes vers des pages en erreur, pages orphelines qu&apos;aucun lien
        n&apos;atteint. Le coût est double : le robot gaspille son passage et le visiteur
        tombe dans le vide. Ces problèmes sont invisibles depuis le site et se détectent
        seulement en suivant chaque lien.
      </p>
      <p>
        <strong>Quatre. Le reste.</strong> Titres et descriptions hors bornes, images sans
        texte alternatif, balises structurées incomplètes. Ça compte, et ça ne compte
        qu&apos;une fois les trois premières familles réglées. Un rapport qui met ces
        quatre familles sur le même plan vous fait commencer par la moins rentable.
      </p>

      <h2>Le piège du score sur cent</h2>
      <p>
        Presque tous les outils d&apos;audit rendent un score global. Il rassure et il
        égare, parce qu&apos;il additionne des problèmes sans commune mesure. Une page
        bloquée à l&apos;indexation et une balise de titre de soixante-dix caractères
        entrent dans le même calcul, alors que la première coûte une page entière et la
        seconde quelques clics.
      </p>
      <p>
        Pire, le score pousse à optimiser le score. On corrige quarante petites choses pour
        passer de 62 à 78, et on laisse en place le seul problème qui coûtait vraiment.
        Une liste courte, ordonnée par conséquence réelle, vaut mieux qu&apos;une jauge.
      </p>

      <h2>Quand refaire l&apos;audit</h2>
      <p>
        Après chaque changement structurel, sans exception. Une refonte, une migration, un
        changement de thème ou l&apos;ajout d&apos;un module introduisent des régressions
        que personne ne voit depuis le navigateur : une redirection perdue, un robots.txt
        écrasé par la configuration par défaut, une balise canonique générée
        automatiquement vers la mauvaise page.
      </p>
      <p>
        Ces régressions se paient en trafic quelques semaines plus tard, quand plus
        personne ne fait le lien avec la mise en ligne. Un audit juste après le déploiement
        coûte dix minutes et évite ce scénario. En dehors des changements, deux passages
        par an suffisent à attraper la dérive lente.
      </p>

      <h2>Transformer le rapport en demande précise</h2>
      <p>
        La valeur d&apos;un audit ne tient pas au nombre de problèmes trouvés mais à la
        précision de ce que vous pouvez demander ensuite. « Le SEO ne marche pas » déclenche
        une réunion. « La page /services/plomberie renvoie un noindex depuis la mise à jour
        du 12, voici l&apos;URL » déclenche une correction dans l&apos;heure.
      </p>
      <p>
        C&apos;est pour ça que le rapport est partageable par lien : votre développeur ou
        votre agence l&apos;ouvre sans compte, voit la liste ordonnée et sait exactement quoi
        toucher. Lancez-le sur l&apos;<Link href="/audit">audit gratuit</Link>, puis
        vérifiez l&apos;effet des corrections avec le{" "}
        <Link href="/suivi-position-google-canada">suivi de position</Link>. Si le problème
        n&apos;est pas technique, la page{" "}
        <Link href="/referencement-pme-quebec">référencement PME Québec</Link> décrit les
        deux autres cas de figure.
      </p>
    </SeoLanding>
  );
}
