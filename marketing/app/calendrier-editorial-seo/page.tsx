import type { Metadata } from "next";
import Link from "next/link";
import { CalendarDays, Layers, ListChecks, Radar, RefreshCw, Target } from "lucide-react";

import { SeoLanding, type Benefit, type FaqItem } from "@/components/SeoLanding";

const PAGE_URL = "https://www.gridar.app/calendrier-editorial-seo";

// Cible mesurée le 2026-08-30. Search Console sur 180 jours :
// "calendrier éditorial seo" pèse 67 impressions en position moyenne 30, sans
// aucune page dédiée sur le site. SERP réel : eskimoz.fr, romanesko.com,
// publisuites.com, klaviyo.com, adimeo.com. gridar.app en est absent.
export const metadata: Metadata = {
  title: { absolute: "Calendrier éditorial SEO : le construire sur des mesures | Gridar" },
  description:
    "Un calendrier éditorial SEO qui part de vos données réelles : mots-clés où vous êtes absent, pages qui s'érodent, grappes incomplètes. Modèle et méthode.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "Calendrier éditorial SEO : arrêter de le remplir au feeling",
    description:
      "Grappes, opportunités mesurées et pages en perte de trafic : les trois sources qui remplissent un calendrier éditorial défendable.",
    url: PAGE_URL,
    type: "website",
    siteName: "Gridar",
    locale: "fr_CA",
  },
  robots: { index: true, follow: true },
};

const FAQ: FaqItem[] = [
  {
    question: "Comment construire un calendrier éditorial SEO ?",
    answer:
      "Pas en listant des idées, mais en partant de trois sources mesurables : les requêtes où vos concurrents apparaissent et vous non, les pages qui perdent des impressions et qu'il faut reprendre avant qu'elles décrochent, et les trous dans vos grappes de contenu existantes. Vous obtenez une file d'attente ordonnée par ce que ça rapporte, pas par ce qui vous inspire le lundi matin.",
  },
  {
    question: "À quelle fréquence faut-il publier ?",
    answer:
      "La bonne cadence est celle que vous tenez douze mois. Un article par semaine abandonné en février fait moins qu'un article aux deux semaines maintenu toute l'année, parce que le référencement récompense la régularité et la profondeur d'un sujet, pas les pointes. Choisissez la cadence en fonction du temps réel de relecture disponible, jamais en fonction d'un objectif de volume.",
  },
  {
    question: "Faut-il écrire un article par mot-clé ?",
    answer:
      "Non, et c'est l'erreur qui produit le plus de cannibalisation. Deux requêtes dont les pages de résultats se ressemblent fortement appellent une seule page. Deux requêtes dont les résultats n'ont presque rien en commun appellent deux pages. Le critère se mesure : on compare les domaines présents dans les deux SERP. En dessous de la moitié en commun, ce sont deux intentions distinctes.",
  },
  {
    question: "Comment prioriser les sujets du calendrier ?",
    answer:
      "Par la distance à la première page, pas par le volume supposé. Une requête où vous êtes en position 12 rapporte plus vite qu'une requête où vous êtes absent, même si la seconde paraît plus grosse. Le classement le plus utile combine trois faits vérifiables : votre position actuelle, la présence de concurrents identifiés, et l'existence d'une page à corriger plutôt qu'à créer.",
  },
  {
    question: "Faut-il aussi planifier les mises à jour, pas seulement les nouveautés ?",
    answer:
      "Oui, et c'est la moitié du calendrier que tout le monde oublie. Un article publié il y a deux ans qui perd 20 % de ses impressions coûte beaucoup moins cher à remonter qu'un nouvel article ne coûte à faire décoller. Réserver une place par mois aux reprises change plus la courbe de trafic que d'ajouter un article de plus.",
  },
  {
    question: "Un outil peut-il remplir le calendrier tout seul ?",
    answer:
      "Il peut remplir la file d'attente, parce qu'elle vient de mesures. Il ne devrait pas décider seul de ce qui est publié : l'angle, le ton et ce que vous refusez de dire vous appartiennent. Gridar propose les sujets classés avec leur preuve et génère les brouillons ; la relecture reste une étape humaine par défaut.",
  },
];

const BENEFITS: Benefit[] = [
  {
    icon: Radar,
    title: "Les sujets viennent d'un SERP",
    text: "Chaque sujet proposé s'appuie sur une page de résultats réellement interrogée, avec les domaines qui l'occupent.",
  },
  {
    icon: RefreshCw,
    title: "Les reprises comptent autant",
    text: "Les pages qui perdent des impressions remontent dans la file, parce qu'elles se réparent moins cher qu'une création.",
  },
  {
    icon: Layers,
    title: "Une grappe, pas une liste",
    text: "Les sujets se regroupent par thème pour construire de l'autorité sur un sujet plutôt que d'éparpiller des articles isolés.",
  },
  {
    icon: Target,
    title: "Classé par distance au top 10",
    text: "Une requête où vous êtes en 12e position passe devant une requête plus grosse où vous êtes invisible.",
  },
  {
    icon: ListChecks,
    title: "Cannibalisation détectée",
    text: "Deux sujets dont les SERP se ressemblent trop fusionnent avant d'être écrits, au lieu de se concurrencer après.",
  },
  {
    icon: CalendarDays,
    title: "Une cadence tenable",
    text: "Le calendrier se cale sur le temps de relecture réellement disponible, pas sur un objectif de volume qui casse en février.",
  },
];

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Calendrier éditorial SEO piloté par la mesure",
  serviceType: "Planification éditoriale SEO",
  description:
    "Construction d'un calendrier éditorial SEO à partir de données mesurées : requêtes où le site est absent, pages en perte d'impressions et grappes de contenu incomplètes.",
  url: PAGE_URL,
  provider: { "@type": "Organization", name: "Gridar", url: "https://www.gridar.app" },
  areaServed: { "@type": "AdministrativeArea", name: "Québec, Canada" },
};

export default function CalendrierEditorialSeoPage() {
  return (
    <SeoLanding
      trail="Calendrier éditorial SEO"
      badge="Méthode et outils gratuits"
      badgeIcon={CalendarDays}
      h1="Calendrier éditorial SEO : le remplir avec des mesures, pas des idées"
      lede="Un calendrier éditorial qui part d'un brainstorm produit des articles que personne ne cherche. Trois sources mesurables suffisent à le remplir pour un an, et à savoir dans quel ordre."
      ctaPrimary={{ href: "/tools/competitor-gap", label: "Trouver mes sujets manquants" }}
      ctaSecondary={{ href: "/audit", label: "Auditer mon site d'abord" }}
      benefitsTitle="Un calendrier qu'on peut défendre en réunion"
      benefits={BENEFITS}
      faqTitle="Questions fréquentes sur le calendrier éditorial SEO"
      faq={FAQ}
      finalCtaTitle="Commencez par la file d'attente, pas par le gabarit"
      finalCtaText="Le détecteur d'écarts vous donne gratuitement les requêtes où vos concurrents apparaissent et vous non, avec la page de résultats en preuve. C'est la première colonne de votre calendrier."
      finalCtaPrimary={{ href: "/tools/competitor-gap", label: "Voir mes écarts gratuitement" }}
      finalCtaSecondary={{ href: "/login", label: "Ouvrir un compte" }}
      jsonLd={serviceJsonLd}
    >
      <h2>Pourquoi la plupart des calendriers éditoriaux ne servent à rien</h2>
      <p>
        Le scénario habituel : une réunion, un tableur, trente idées de titres, une
        colonne de dates. Trois mois plus tard, six articles sont publiés, aucun ne se
        classe, et le calendrier est abandonné parce qu&apos;il ne produisait rien de
        mesurable. Le problème n&apos;était pas la discipline, il était la source des
        sujets.
      </p>
      <p>
        Un sujet issu d&apos;un brainstorm répond à une question que votre équipe se pose.
        Un sujet issu d&apos;une page de résultats répond à une question que vos clients
        tapent. Ce n&apos;est pas la même chose, et l&apos;écart explique la plupart des
        blogues d&apos;entreprise qui tournent à vide depuis des années.
      </p>
      <p>
        La correction est mécanique : remplacer l&apos;étape « on cherche des idées » par
        « on lit ce qui existe déjà ». Le reste du calendrier, la cadence, les
        responsables, les dates, fonctionne exactement pareil.
      </p>

      <h2>Les trois sources qui remplissent un calendrier</h2>
      <p>
        <strong>Un. Les requêtes où vos concurrents sont et vous non.</strong> C&apos;est
        la source la plus directe : quelqu&apos;un occupe déjà une page de résultats sur
        laquelle vous êtes absent, donc la demande existe et le format qui fonctionne est
        visible. Le <Link href="/tools/competitor-gap">détecteur d&apos;écarts</Link>{" "}
        interroge de vraies pages de résultats et rend chaque écart avec les domaines qui
        l&apos;occupent.
      </p>
      <p>
        <strong>Deux. Les pages qui perdent des impressions.</strong> Un article qui
        décroche lentement est la meilleure affaire du calendrier : la page existe déjà,
        elle a de l&apos;ancienneté, et une reprise coûte une fraction d&apos;une
        création. Repérer la baisse tôt est tout le sujet, parce que la même page
        redevient coûteuse une fois qu&apos;elle est sortie du top 20.
      </p>
      <p>
        <strong>Trois. Les trous dans vos grappes.</strong> Si vous avez cinq articles sur
        un thème et qu&apos;il manque la question centrale que tout le monde pose, la
        grappe entière plafonne. Compléter un thème existant rapporte davantage
        qu&apos;ouvrir un thème neuf, parce que les pages existantes se renforcent
        mutuellement par le maillage.
      </p>

      <h2>Dans quel ordre publier</h2>
      <p>
        Le réflexe est de classer par volume de recherche supposé. C&apos;est le pire
        critère disponible, pour deux raisons. Le volume exact n&apos;est pas accessible
        sans campagne publicitaire active, donc le chiffre affiché par la plupart des
        outils est une estimation. Et même exact, il ne dit rien de votre capacité à vous
        classer sur cette requête.
      </p>
      <p>
        Le critère utile est la <strong>distance à la première page</strong>. Une requête
        où vous êtes en position 12 demande une amélioration de page, quelques liens
        internes et une mise à jour ; elle peut basculer en semaines. Une requête où vous
        êtes absent demande une page entière et de la patience. À effort égal, la première
        rapporte d&apos;abord.
      </p>
      <p>
        Le deuxième critère est la présence de concurrents identifiés. Une requête que
        votre marché occupe vaut mieux qu&apos;une requête que personne ne dispute :
        l&apos;absence totale de concurrence signale presque toujours l&apos;absence de
        demande commerciale.
      </p>

      <h2>Un sujet ou deux ? La question qui évite la cannibalisation</h2>
      <p>
        Deux requêtes proches posent toujours la même question : une page ou deux. La
        réponse se mesure au lieu de se deviner. Comparez les pages de résultats des deux
        requêtes et comptez les domaines communs. Au-dessus de la moitié, Google considère
        que c&apos;est la même intention : une seule page, sinon vos deux pages se
        disputent la même place et perdent toutes les deux.
      </p>
      <p>
        En dessous de la moitié, ce sont deux intentions distinctes et deux pages se
        justifient. Cette vérification prend deux minutes et évite le travail le plus
        coûteux du référencement : fusionner après coup deux articles publiés, en gérant
        les redirections et les liens qui pointaient vers le perdant.
      </p>

      <h2>La cadence, et la place réservée aux reprises</h2>
      <p>
        Choisissez la cadence sur le temps de relecture réellement disponible. Un article
        aux deux semaines tenu douze mois bat un article par semaine abandonné au
        troisième. Le référencement récompense la profondeur d&apos;un sujet et la
        régularité, pas les pointes de production.
      </p>
      <p>
        Réservez ensuite une place par mois aux mises à jour. C&apos;est la moitié du
        calendrier que presque personne ne planifie, et celle qui déplace le plus la
        courbe. Une page de deux ans remise à jour retrouve souvent sa position en
        quelques semaines ; un article neuf met des mois à exister.
      </p>
      <p>
        Pour construire la première version de votre file, commencez par les écarts
        mesurés, puis vérifiez l&apos;état technique du site avec l&apos;
        <Link href="/audit">audit gratuit</Link> : publier sur un site qui bloque
        l&apos;indexation revient à écrire pour personne. Et si vous voulez suivre
        l&apos;effet de chaque publication, le{" "}
        <Link href="/suivi-position-google-canada">suivi de position</Link> donne le rang
        réel sur Google.ca, ville par ville.
      </p>
    </SeoLanding>
  );
}
