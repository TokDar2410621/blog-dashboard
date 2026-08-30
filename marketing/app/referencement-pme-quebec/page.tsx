import type { Metadata } from "next";
import Link from "next/link";
import { Building2, Coins, Languages, MapPin, Scale, Timer } from "lucide-react";

import { SeoLanding, type Benefit, type FaqItem } from "@/components/SeoLanding";

const PAGE_URL = "https://www.gridar.app/referencement-pme-quebec";

// Cible mesurée le 2026-08-30. Search Console sur 180 jours : le groupe PME
// pèse environ 85 impressions ("référencement pme québec" 35 en position 80,
// "référencement naturel pour pme" 25 en position 83, "seo pour pme" 25 en
// position 68), sans page dédiée. SERP réel : referencement-pme.ca,
// socialinfluencebuilder.com, matlo.ca, cyberperformance.ca, abcnumerique.ca.
// gridar.app en est absent.
export const metadata: Metadata = {
  title: { absolute: "Référencement PME Québec : par où commencer | Gridar" },
  description:
    "Le référencement d'une PME québécoise ne se joue pas au niveau du pays mais de la ville, et pas en anglais. Les priorités réelles, dans l'ordre, et ce qui se mesure.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "Référencement PME Québec : les priorités dans le bon ordre",
    description:
      "Google.ca en français, géolocalisé par ville, et un budget qui ne permet pas de tout faire. Ce qu'une PME québécoise doit régler en premier.",
    url: PAGE_URL,
    type: "website",
    siteName: "Gridar",
    locale: "fr_CA",
  },
  robots: { index: true, follow: true },
};

const FAQ: FaqItem[] = [
  {
    question: "Combien coûte le référencement pour une PME au Québec ?",
    answer:
      "Les modèles vont de quelques centaines de dollars par mois pour un accompagnement léger à plusieurs milliers pour une agence complète. Le chiffre utile n'est pas le prix mais ce qu'il achète : une PME qui paie pour des rapports mensuels sans jamais voir une page corrigée paie cher. Avant d'engager un budget, mesurez l'état réel du site : l'audit est gratuit et sans inscription, et il révèle souvent que les premiers gains sont techniques et gratuits.",
  },
  {
    question: "Pourquoi mes positions diffèrent selon la ville ?",
    answer:
      "Parce que Google tient compte de la proximité. Un commerce près de la personne qui cherche a plus de chances d'apparaître, donc on peut être premier à Montréal et absent à Saguenay pour le même mot-clé. Pour une PME, c'est une bonne nouvelle : vous n'avez pas à battre le Canada, seulement votre ville et votre région. Un suivi qui ne précise pas la ville donne une moyenne qui ne correspond à la réalité d'aucun client.",
  },
  {
    question: "Faut-il une version anglaise du site ?",
    answer:
      "Seulement si des clients achètent en anglais. Une version anglaise double le travail de rédaction et de maintenance, et elle ne rapporte rien si votre clientèle est francophone. Quand elle est justifiée, elle doit être une vraie traduction relue avec ses propres balises de langue, pas une traduction automatique branchée sur le site, qui produit des pages faibles dans les deux langues.",
  },
  {
    question: "Google My Business suffit-il pour une PME locale ?",
    answer:
      "La fiche est indispensable et elle ne suffit pas. Elle vous place dans le bloc de trois résultats avec la carte, ce qui capte une partie des recherches locales. Elle ne vous place pas dans les résultats organiques en dessous, qui répondent aux questions précises que tapent vos clients avant de choisir. Les deux se travaillent ensemble : la fiche pour la proximité, le site pour les questions.",
  },
  {
    question: "Combien de temps avant de voir des résultats ?",
    answer:
      "Les corrections techniques agissent en quelques semaines quand elles débloquent une indexation. Le contenu se compte en mois, parce qu'une page neuve doit être découverte, évaluée, puis progressivement remontée. Le repère honnête pour une PME : trois mois pour voir bouger les positions sur des requêtes où vous êtes déjà en page deux, six à douze mois pour des requêtes où vous êtes absent.",
  },
  {
    question: "Les outils internationaux conviennent-ils au marché québécois ?",
    answer:
      "Ils mesurent très bien et sous-estiment systématiquement le français québécois. Leur suivi de position fonctionne au niveau du pays, rarement de la ville, et leurs estimations de volume ignorent une bonne partie des formulations d'ici. Pour une PME dont tout le marché tient dans une région, cette imprécision fait prendre les mauvaises décisions, parce qu'elle masque exactement les requêtes que vous pourriez gagner.",
  },
];

const BENEFITS: Benefit[] = [
  {
    icon: MapPin,
    title: "Mesuré ville par ville",
    text: "Les positions sont relevées sur Google.ca géolocalisé, parce qu'une moyenne nationale ne décrit le quotidien d'aucun de vos clients.",
  },
  {
    icon: Languages,
    title: "En français du Québec",
    text: "Les requêtes d'ici ne sont pas celles de France, et les outils internationaux les sous-estiment presque toujours.",
  },
  {
    icon: Coins,
    title: "Les gains gratuits d'abord",
    text: "Une bonne part des premiers gains est technique et ne coûte que du temps. Aucune raison de payer avant de les avoir pris.",
  },
  {
    icon: Scale,
    title: "Une priorité, pas une liste",
    text: "Un rapport de 80 points est inutile à une PME. Ce qui sert, c'est de savoir quoi corriger cette semaine.",
  },
  {
    icon: Timer,
    title: "Des délais annoncés honnêtement",
    text: "Trois mois pour remonter d'une page deux, six à douze mois pour exister sur une requête neuve. Le reste est de la vente.",
  },
  {
    icon: Building2,
    title: "Adapté aux petites équipes",
    text: "Les recommandations tiennent compte du fait que personne, chez vous, n'a le SEO comme métier à temps plein.",
  },
];

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Référencement naturel pour les PME du Québec",
  serviceType: "SEO local et technique pour PME",
  description:
    "Audit technique, suivi des positions sur Google.ca géolocalisé par ville québécoise, détection d'opportunités face aux concurrents et production de contenu, pensés pour les PME du Québec.",
  url: PAGE_URL,
  provider: { "@type": "Organization", name: "Gridar", url: "https://www.gridar.app" },
  areaServed: { "@type": "AdministrativeArea", name: "Québec, Canada" },
};

export default function ReferencementPmeQuebecPage() {
  return (
    <SeoLanding
      trail="Référencement PME Québec"
      badge="Audit gratuit, sans inscription"
      badgeIcon={MapPin}
      h1="Référencement PME Québec : les priorités dans le bon ordre"
      lede="Une PME québécoise n'a pas à battre le Canada, seulement sa ville et sa région. Ça change complètement l'ordre des priorités, et ça rend les premiers gains beaucoup plus accessibles qu'on ne le croit."
      ctaPrimary={{ href: "/audit", label: "Auditer mon site gratuitement" }}
      ctaSecondary={{ href: "/suivi-position-google-canada", label: "Vérifier ma position" }}
      benefitsTitle="Pensé pour le marché d'ici"
      benefits={BENEFITS}
      faqTitle="Questions fréquentes sur le référencement des PME au Québec"
      faq={FAQ}
      finalCtaTitle="Mesurez avant d'engager un budget"
      finalCtaText="L'audit technique est gratuit, sans inscription, et il révèle souvent que les premiers gains ne coûtent que du temps. Vous saurez ensuite si vous avez un problème technique, éditorial ou concurrentiel."
      finalCtaPrimary={{ href: "/audit", label: "Lancer l'audit gratuit" }}
      finalCtaSecondary={{ href: "/tools", label: "Explorer les outils" }}
      jsonLd={serviceJsonLd}
    >
      <h2>Ce qui change quand le marché tient dans une région</h2>
      <p>
        Le référencement enseigné dans la plupart des ressources vise des marchés
        nationaux ou internationaux : autorité de domaine, netlinking, volumes de
        recherche à cinq chiffres. Une PME de Trois-Rivières, de Rimouski ou de Saguenay
        n&apos;est pas dans ce jeu, et essayer d&apos;y jouer est le meilleur moyen de
        dépenser sans résultat.
      </p>
      <p>
        Votre concurrence réelle n&apos;est pas mondiale, elle tient sur une page de
        résultats géolocalisée. Google privilégie la proximité, donc vous n&apos;avez pas
        à dépasser des sites nationaux : vous avez à dépasser les quelques entreprises de
        votre région qui répondent à la même question. C&apos;est une compétition
        beaucoup plus gagnable, et elle demande d&apos;autres priorités.
      </p>
      <p>
        La conséquence pratique : un suivi de position qui ne précise pas la ville ne vous
        apprend rien. Vous pouvez être premier chez vous et absent à quarante kilomètres,
        et la moyenne des deux ne décrit la réalité d&apos;aucun client. Le{" "}
        <Link href="/suivi-position-google-canada">vérificateur de position</Link> relève
        le rang par ville québécoise, gratuitement.
      </p>

      <h2>Les trois priorités, dans cet ordre</h2>
      <p>
        <strong>Un. Ce qui empêche Google de lire le site.</strong> Une page bloquée à
        l&apos;indexation, un rendu qui dépend du JavaScript, des redirections en chaîne,
        des liens morts : tant que ces problèmes existent, tout le reste est du travail
        perdu. C&apos;est aussi la partie la moins chère, parce qu&apos;elle se corrige une
        fois et ne se refait pas. L&apos;<Link href="/audit">audit gratuit</Link> la relève
        sans inscription.
      </p>
      <p>
        <strong>Deux. Ce que vos clients tapent réellement.</strong> Les mots que vous
        utilisez à l&apos;interne sont rarement ceux de vos clients, et les requêtes
        québécoises diffèrent souvent des formulations de France. La seule source fiable
        est la page de résultats elle-même : qui s&apos;y trouve, sous quel format, avec
        quel angle. Le{" "}
        <Link href="/tools/competitor-gap">détecteur d&apos;écarts</Link> montre les
        requêtes où vos concurrents apparaissent et vous non.
      </p>
      <p>
        <strong>Trois. Les pages qui manquent.</strong> Une PME a presque toujours une
        page d&apos;accueil, une page services qui énumère tout, et un formulaire de
        contact. Google ne sait pas quoi faire d&apos;une page qui parle de six services :
        elle ne se classe sur aucun. Une page par service réellement offert, écrite avec
        les mots du client, change davantage la courbe que n&apos;importe quel article de
        blogue.
      </p>

      <h2>Ce qui coûte cher et rapporte peu</h2>
      <p>
        <strong>Les rapports mensuels sans exécution.</strong> Un contrat qui produit un
        tableau de bord tous les mois sans qu&apos;une page soit corrigée facture de la
        mesure, pas du référencement. La mesure est utile et elle est presque gratuite ;
        ce qui coûte, c&apos;est le travail qui suit.
      </p>
      <p>
        <strong>Le volume d&apos;articles.</strong> Publier deux articles par semaine sur
        des sujets que personne ne cherche produit un blogue chargé et zéro visiteur. La
        régularité compte, mais seulement appliquée à des sujets choisis sur des mesures.
        La page{" "}
        <Link href="/calendrier-editorial-seo">calendrier éditorial SEO</Link> détaille
        comment remplir la file autrement qu&apos;au feeling.
      </p>
      <p>
        <strong>Une version anglaise par réflexe.</strong> Si vos clients achètent en
        français, une version anglaise double le travail sans rapporter. Elle se justifie
        quand des acheteurs hors Québec existent vraiment, et elle demande alors une vraie
        traduction relue, pas un module automatique.
      </p>

      <h2>Ce qu&apos;il est honnête d&apos;attendre, et quand</h2>
      <p>
        Les corrections techniques agissent vite quand elles débloquent quelque chose :
        une page qui n&apos;était pas indexable peut apparaître en quelques semaines. Les
        gains de position sur des requêtes où vous êtes déjà en page deux se comptent en
        semaines à quelques mois, parce que la page existe et qu&apos;il s&apos;agit de
        l&apos;améliorer.
      </p>
      <p>
        Les requêtes où vous êtes totalement absent demandent six à douze mois. La page
        doit être écrite, découverte, évaluée, puis remontée progressivement. Tout
        prestataire qui promet la première page en trois mois sur une requête disputée
        vend une chose qu&apos;il ne contrôle pas.
      </p>
      <p>
        Le repère qui compte pour une PME n&apos;est d&apos;ailleurs pas la position mais
        l&apos;appel. Une remontée de la douzième à la sixième place sur une requête que
        cinquante personnes tapent chaque mois dans votre ville vaut mieux qu&apos;une
        première place sur un terme national qui n&apos;amène personne chez vous.
      </p>

      <h2>Par où commencer cette semaine</h2>
      <p>
        Lancez l&apos;<Link href="/audit">audit gratuit</Link> : il vous dit en quelques
        minutes si votre problème est technique. Vérifiez ensuite deux ou trois positions
        réelles dans votre ville avec le{" "}
        <Link href="/suivi-position-google-canada">suivi de position</Link>. Ces deux
        mesures suffisent à savoir si vous devez corriger, écrire, ou les deux, et elles ne
        coûtent rien.
      </p>
      <p>
        Si vous voulez aller plus loin sans engager de budget, les{" "}
        <Link href="/tools">outils gratuits</Link> couvrent la difficulté d&apos;un
        mot-clé, les écarts face aux concurrents et votre visibilité dans les réponses des
        IA, qui devient un canal de découverte réel pour les entreprises locales.
      </p>
    </SeoLanding>
  );
}
