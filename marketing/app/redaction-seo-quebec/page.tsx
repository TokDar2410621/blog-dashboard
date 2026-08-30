import type { Metadata } from "next";
import Link from "next/link";
import { Eye, FileText, Languages, PenLine, Target, UserCheck } from "lucide-react";

import { SeoLanding, type Benefit, type FaqItem } from "@/components/SeoLanding";

const PAGE_URL = "https://www.gridar.app/redaction-seo-quebec";

// Cible mesurée le 2026-08-30 par la pipeline de découverte : Google suggère
// "redaction seo quebec prix" et "redaction seo quebec tarifs", le SERP est
// commercial et gridar.app en est absent. Occupé par bolle.ca,
// sarahtailleur.com, digitad.ca, effetmonstre.com, affichez.ca, ganeo.ca.
//
// Aucune page du site ne traitait la production de contenu vue du client.
export const metadata: Metadata = {
  title: { absolute: "Rédaction SEO au Québec : prix, méthode et limites | Gridar" },
  description:
    "Ce que coûte la rédaction SEO au Québec, ce qui fait varier le prix, et où se situe la génération assistée par IA. Sans promesse de mots-clés magiques.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "Rédaction SEO au Québec : prix, méthode et limites",
    description:
      "Rédacteur, agence ou génération assistée : ce que chaque option coûte vraiment et ce qu'elle règle. Écrit sans détour.",
    url: PAGE_URL,
    type: "website",
    siteName: "Gridar",
    locale: "fr_CA",
  },
  robots: { index: true, follow: true },
};

const FAQ: FaqItem[] = [
  {
    question: "Combien coûte la rédaction SEO au Québec ?",
    answer:
      "Les modèles courants vont d'environ 0,15 $ à 0,50 $ le mot chez un pigiste, à quelques centaines de dollars par article chez une agence, selon la recherche exigée et le niveau d'expertise du sujet. Un article technique qui demande de comprendre un métier coûte plus cher qu'un texte généraliste, et c'est normal. Le chiffre à surveiller n'est pas le prix au mot mais le coût par article publié qui se classe, parce qu'un texte pas cher qui n'attire personne coûte l'infini.",
  },
  {
    question: "Faut-il écrire en français de France ou du Québec ?",
    answer:
      "En français d'ici, si vos clients sont ici. Les formulations diffèrent plus qu'on ne le pense, et les requêtes tapées au Québec ne sont pas toujours celles de France : le vocabulaire des métiers, les noms de services et même les unités changent. Un texte écrit pour la France se classe mal ici, non pas parce que Google le pénalise, mais parce qu'il ne contient pas les mots que vos clients tapent.",
  },
  {
    question: "Un article généré par IA peut-il se classer ?",
    answer:
      "Oui, et Google l'a dit explicitement : ce qui compte est l'utilité du contenu, pas la façon dont il a été produit. Ce qui ne se classe pas, c'est le texte générique qui répète ce que dix autres pages disent déjà, qu'il soit écrit par une machine ou par un humain pressé. La différence se joue sur ce que vous êtes seul à pouvoir dire : vos prix, vos délais, vos cas particuliers, ce que vous refusez de prendre.",
  },
  {
    question: "Quelle longueur pour un article SEO ?",
    answer:
      "Celle qu'il faut pour répondre, pas un objectif fixé d'avance. Le repère utile se lit sur la page de résultats : si les pages qui se classent font 800 mots, en écrire 3000 ne vous avantage pas, ça dilue. Si elles en font 2500, un texte de 600 mots aura du mal à convaincre. La longueur est une conséquence du sujet, jamais un objectif.",
  },
  {
    question: "Combien d'articles faut-il publier par mois ?",
    answer:
      "Moins que ce que la plupart des offres proposent, et plus régulièrement. Quatre articles par mois abandonnés au troisième mois valent moins que deux articles par mois tenus un an. La régularité et la profondeur sur un même thème comptent davantage que le volume, parce que c'est la grappe de contenu qui construit l'autorité, pas la somme d'articles isolés.",
  },
  {
    question: "Gridar remplace-t-il un rédacteur ?",
    answer:
      "Non, et ce serait malhonnête de le laisser croire. Gridar génère des brouillons à partir de vos mots-clés suivis et de la mémoire de votre site, ce qui supprime la page blanche et la recherche de structure. La relecture reste humaine par défaut, parce qu'un texte qui se trompe sur vos prix ou vos zones desservies vous coûte plus cher que les heures gagnées. Pour un contenu de marque à fort enjeu, un rédacteur reste le bon choix.",
  },
];

const BENEFITS: Benefit[] = [
  {
    icon: Target,
    title: "Le sujet vient d'un SERP",
    text: "Un brouillon utile part d'une requête que des gens tapent, pas d'une idée de réunion. La preuve accompagne le sujet.",
  },
  {
    icon: Languages,
    title: "En français d'ici",
    text: "Les mots que tapent vos clients au Québec ne sont pas toujours ceux de France, et l'écart se voit dans les positions.",
  },
  {
    icon: UserCheck,
    title: "Relecture humaine par défaut",
    text: "Les brouillons attendent votre validation. Un texte qui se trompe sur vos prix coûte plus que les heures qu'il fait gagner.",
  },
  {
    icon: Eye,
    title: "La mémoire de votre site",
    text: "Ce que vous vendez, à qui, et ce que vous refusez : le brouillon part de ce contexte plutôt que d'un gabarit générique.",
  },
  {
    icon: PenLine,
    title: "La longueur suit le sujet",
    text: "Le repère se lit sur la page de résultats. Écrire trois fois plus long que les pages qui se classent dilue au lieu d'aider.",
  },
  {
    icon: FileText,
    title: "Une grappe, pas une pile",
    text: "Les articles se regroupent par thème pour construire de l'autorité, au lieu de s'accumuler sans se renforcer.",
  },
];

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Production de contenu SEO assistée, pour le marché québécois",
  serviceType: "Rédaction et génération de contenu SEO",
  description:
    "Génération de brouillons d'articles SEO à partir de mots-clés suivis et de la mémoire du site, en français du Québec, avec relecture humaine par défaut avant publication.",
  url: PAGE_URL,
  provider: { "@type": "Organization", name: "Gridar", url: "https://www.gridar.app" },
  areaServed: { "@type": "AdministrativeArea", name: "Québec, Canada" },
};

export default function RedactionSeoQuebecPage() {
  return (
    <SeoLanding
      trail="Rédaction SEO Québec"
      badge="Outils de recherche gratuits"
      badgeIcon={PenLine}
      h1="Rédaction SEO au Québec : prix, méthode et limites"
      lede="Ce que coûte vraiment un article, ce qui fait varier la facture, et où se situe honnêtement la génération assistée par IA. Sans promesse de mots-clés magiques ni de première place en trois mois."
      ctaPrimary={{ href: "/tools/competitor-gap", label: "Trouver mes sujets" }}
      ctaSecondary={{ href: "/audit", label: "Auditer mon site d'abord" }}
      benefitsTitle="Ce qui distingue un article qui se classe"
      benefits={BENEFITS}
      faqTitle="Questions fréquentes sur la rédaction SEO au Québec"
      faq={FAQ}
      finalCtaTitle="Commencez par le sujet, pas par le texte"
      finalCtaText="Le détecteur d'écarts vous donne gratuitement les requêtes où vos concurrents apparaissent et vous non, avec la page de résultats en preuve. Un bon sujet vaut mieux qu'un bon texte sur le mauvais sujet."
      finalCtaPrimary={{ href: "/tools/competitor-gap", label: "Voir mes sujets manquants" }}
      finalCtaSecondary={{ href: "/login", label: "Ouvrir un compte" }}
      jsonLd={serviceJsonLd}
    >
      <h2>Ce qui fait varier le prix, vraiment</h2>
      <p>
        Les grilles affichées au Québec vont d&apos;environ 0,15 $ à 0,50 $ le mot chez un
        pigiste, et de quelques centaines de dollars par article chez une agence. L&apos;
        écart ne vient presque jamais de la qualité de l&apos;écriture, qui se ressemble
        beaucoup d&apos;un prestataire à l&apos;autre. Il vient de trois choses.
      </p>
      <p>
        <strong>La recherche en amont.</strong> Choisir le sujet à partir de vraies pages
        de résultats, lire ce que font les pages qui se classent, repérer l&apos;angle
        manquant : c&apos;est le travail qui décide du résultat, et c&apos;est celui qu&apos;on
        coupe en premier quand le prix serre.
      </p>
      <p>
        <strong>La connaissance du métier.</strong> Un texte sur un sujet technique demande
        de comprendre le métier avant d&apos;écrire. Ça se paie, et c&apos;est justifié,
        parce que c&apos;est exactement ce qui rend le texte non générique.
      </p>
      <p>
        <strong>Le nombre de relectures.</strong> Une passe d&apos;aller-retour avec vous
        coûte du temps et améliore beaucoup. Zéro passe donne un texte propre qui ne dit
        rien de spécifique à votre entreprise.
      </p>
      <p>
        Le chiffre à surveiller n&apos;est donc pas le prix au mot mais le coût par article
        <em> qui se classe</em>. Un article à 80 $ que personne ne trouve n&apos;est pas
        moins cher qu&apos;un article à 400 $ qui amène des appels : il coûte simplement
        80 $ pour rien.
      </p>

      <h2>Écrire en français d&apos;ici, ce n&apos;est pas une coquetterie</h2>
      <p>
        Les requêtes tapées au Québec diffèrent de celles tapées en France plus souvent
        qu&apos;on ne le croit. Les noms de métiers, les termes de services, les unités et
        même la façon de formuler une question changent. Un texte rédigé pour la France ne
        se classe pas mal parce que Google le pénalise, mais parce qu&apos;il ne contient
        tout simplement pas les mots que vos clients tapent.
      </p>
      <p>
        Le contrôle est simple et gratuit : prenez la formulation que vous comptez utiliser,
        vérifiez qu&apos;elle est bien celle qui remonte sur Google.ca, et regardez qui se
        classe dessus. Le{" "}
        <Link href="/tools/keyword-difficulty">vérificateur de difficulté</Link> et le{" "}
        <Link href="/tools/competitor-gap">détecteur d&apos;écarts</Link> font cette
        vérification sur de vraies pages de résultats.
      </p>

      <h2>Où se situe honnêtement la génération assistée par IA</h2>
      <p>
        Google a été clair : ce qui compte est l&apos;utilité du contenu, pas la façon dont
        il a été produit. Un article généré peut se classer, et un article humain générique
        ne se classe pas. La ligne n&apos;est donc pas machine contre humain, elle est
        spécifique contre interchangeable.
      </p>
      <p>
        Ce qu&apos;une génération assistée fait bien : supprimer la page blanche, produire
        une structure cohérente, couvrir les questions attendues sur un sujet, et le faire
        en quelques minutes plutôt qu&apos;en quelques heures. Sur un besoin de volume
        raisonnable, le gain de temps est réel.
      </p>
      <p>
        Ce qu&apos;elle ne fait pas : connaître vos prix, vos délais réels, votre zone de
        service, le cas particulier que vous refusez de prendre, l&apos;anecdote client qui
        rend une page crédible. Ces éléments sont précisément ceux qui distinguent votre
        page de dix autres, et ils viennent de vous.
      </p>
      <p>
        C&apos;est pourquoi les brouillons produits par Gridar attendent une relecture par
        défaut. Publier sans relire reste techniquement possible et reste votre décision,
        pas la nôtre. Un texte qui se trompe sur vos tarifs ou vos zones desservies coûte
        plus cher que toutes les heures qu&apos;il fait gagner.
      </p>

      <h2>Longueur, fréquence, et les deux quotas qui font du mal</h2>
      <p>
        <strong>La longueur ne devrait jamais être un objectif.</strong> Le repère se lit
        sur la page de résultats : regardez ce que font les pages déjà classées. Si elles
        font 800 mots, en écrire 3000 dilue votre propos sans avantage. Si elles en font
        2500, un texte de 600 mots ne convaincra ni le lecteur ni le moteur.
      </p>
      <p>
        <strong>La fréquence doit être tenable.</strong> Quatre articles par mois abandonnés
        au troisième mois valent moins que deux articles par mois tenus un an. Choisissez la
        cadence sur le temps de relecture réellement disponible, parce que c&apos;est la
        relecture qui manque toujours en premier, pas la rédaction.
      </p>
      <p>
        Une place par mois devrait d&apos;ailleurs aller aux mises à jour plutôt qu&apos;aux
        créations. Un article de deux ans qui perd des impressions se remonte pour une
        fraction du coût d&apos;un article neuf, et il produit un effet plus rapide parce
        que la page existe déjà.
      </p>

      <h2>Rédacteur, agence ou outil : lequel pour quoi</h2>
      <p>
        <strong>Un rédacteur</strong> reste le bon choix pour les pages à fort enjeu : la
        page d&apos;accueil, les pages de service qui portent la vente, un contenu de marque
        où le ton compte autant que le fond.
      </p>
      <p>
        <strong>Une agence</strong> a du sens quand vous voulez déléguer la chaîne complète,
        de la stratégie à la publication, et que vous acceptez d&apos;en payer la
        coordination.
      </p>
      <p>
        <strong>Un outil</strong> a du sens pour le volume intermédiaire : les articles qui
        répondent à des questions précises, nombreux, nécessaires, et qu&apos;aucun budget
        ne justifierait de faire écrire un par un. C&apos;est exactement cette zone que
        couvre la génération assistée.
      </p>
      <p>
        Quel que soit le choix, commencez par le sujet. Un excellent texte sur une requête
        que personne ne tape ne rapporte rien, et c&apos;est de loin l&apos;erreur la plus
        coûteuse. La page{" "}
        <Link href="/referencement-pme-quebec">référencement PME Québec</Link> décrit
        l&apos;ordre des priorités quand le budget ne permet pas de tout faire.
      </p>
    </SeoLanding>
  );
}
