import type { Metadata } from "next";
import Link from "next/link";
import { CalendarClock, Eye, FileText, Link2, Printer, ShieldCheck } from "lucide-react";

import { SeoLanding, type Benefit, type FaqItem } from "@/components/SeoLanding";

const PAGE_URL = "https://www.gridar.app/rapport-seo-automatique";

// Cible mesurée le 2026-08-30. Search Console sur 180 jours :
// "reporting référencement" pèse 34 impressions en position 90, sans page
// dédiée. SERP réel des requêtes voisines : fr.dashthis.com, redacteur.com,
// seoptimer.com, fr.semrush.com, rablab.ca. gridar.app est absent des trois
// requêtes vérifiées ("reporting référencement", "reporting seo automatique",
// "rapport seo automatique").
export const metadata: Metadata = {
  title: { absolute: "Rapport SEO automatique : ce qu'il doit contenir | Gridar" },
  description:
    "Un rapport SEO utile tient sur une page, date chaque chiffre et se partage par lien. Ce qu'il faut y mettre, ce qu'il faut en retirer, et pourquoi.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "Rapport SEO automatique : ce qu'il doit contenir, et ce qu'il faut retirer",
    description:
      "Chiffres datés, sources nommées, une page partageable par lien. Le contraire d'un PDF de quarante pages que personne n'ouvre.",
    url: PAGE_URL,
    type: "website",
    siteName: "Gridar",
    locale: "fr_CA",
  },
  robots: { index: true, follow: true },
};

const FAQ: FaqItem[] = [
  {
    question: "Que doit contenir un rapport SEO ?",
    answer:
      "Quatre choses, et peu d'autres. Ce qui a bougé depuis le dernier rapport, avec le sens du mouvement. Ce qui a été fait pendant la période. Ce qui est cassé et bloque le reste. Ce qui est prévu ensuite. Tout le reste, les scores composites, les graphiques de vanité et les captures d'outils tiers, allonge le document sans changer une seule décision.",
  },
  {
    question: "À quelle fréquence produire un rapport SEO ?",
    answer:
      "La fréquence doit suivre le rythme des décisions, pas le calendrier de facturation. Un rapport hebdomadaire convient quand quelqu'un agit chaque semaine ; sinon il devient un courriel qu'on archive sans lire. Le mensuel suffit à la plupart des PME. Ce qui compte davantage que la fréquence, c'est que chaque chiffre porte sa date de mesure.",
  },
  {
    question: "Pourquoi mon rapport affiche des chiffres différents de Search Console ?",
    answer:
      "Parce que les deux ne mesurent pas la même chose. Search Console rapporte ce que Google a enregistré, avec un décalage de deux à trois jours et un échantillonnage sur les longues périodes. Un relevé de position interroge une page de résultats à un instant précis, depuis une localisation précise. Les deux sont justes ; un rapport honnête dit laquelle des deux sources il utilise pour chaque chiffre.",
  },
  {
    question: "Un rapport automatique peut-il se tromper ?",
    answer:
      "Oui, et le mode d'erreur le plus dangereux est silencieux : une source qui échoue et un rapport qui affiche zéro au lieu de dire que la mesure a échoué. Un zéro se lit comme un effondrement et déclenche de mauvaises réactions. La règle appliquée dans Gridar est de rendre la raison de l'échec, jamais un zéro fabriqué.",
  },
  {
    question: "Comment partager le rapport avec un client ou un patron ?",
    answer:
      "Par un lien plutôt que par une pièce jointe. Un lien reste à jour, s'ouvre sur un téléphone, ne se perd pas dans une boîte de réception et s'imprime en PDF si quelqu'un y tient. Gridar produit des rapports partageables par lien, avec un jeton propre à chaque partage, pour que la personne n'ait pas besoin d'un compte.",
  },
  {
    question: "Faut-il un score SEO global dans le rapport ?",
    answer:
      "Un score unique rassure et n'aide pas. Il additionne des choses qui n'ont pas la même conséquence : une balise trop longue et une page bloquée à l'indexation ne coûtent pas la même chose, et un score les mélange. Ce qui aide, c'est une courte liste ordonnée par impact réel, avec la correction attendue pour chaque ligne.",
  },
];

const BENEFITS: Benefit[] = [
  {
    icon: CalendarClock,
    title: "Chaque chiffre porte sa date",
    text: "Un nombre affiché sans sa date de mesure se lit comme s'il datait d'aujourd'hui. C'est ainsi qu'on décide sur du passé.",
  },
  {
    icon: ShieldCheck,
    title: "Un échec se dit, pas un zéro",
    text: "Quand une source ne répond pas, le rapport affiche la raison. Un zéro inventé se lit comme un effondrement.",
  },
  {
    icon: Link2,
    title: "Partageable par lien",
    text: "Un jeton par partage, aucune inscription pour la personne qui reçoit, et le contenu reste à jour à l'ouverture.",
  },
  {
    icon: Printer,
    title: "Imprimable en PDF",
    text: "Pour les contextes où une pièce jointe reste exigée, la même page s'imprime proprement sans version parallèle à maintenir.",
  },
  {
    icon: Eye,
    title: "Les sources sont nommées",
    text: "Search Console, relevé de SERP, exploration du site : on sait d'où vient chaque chiffre, donc on sait quoi en conclure.",
  },
  {
    icon: FileText,
    title: "Court par conception",
    text: "Ce qui a bougé, ce qui a été fait, ce qui bloque, ce qui suit. Un rapport de quarante pages n'est pas lu, donc il ne sert à rien.",
  },
];

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Rapports SEO automatiques et partageables",
  serviceType: "Reporting SEO",
  description:
    "Production de rapports SEO datés et partageables par lien : positions relevées, travaux effectués, problèmes techniques bloquants et suites prévues, avec la source de chaque chiffre.",
  url: PAGE_URL,
  provider: { "@type": "Organization", name: "Gridar", url: "https://www.gridar.app" },
  areaServed: { "@type": "AdministrativeArea", name: "Québec, Canada" },
};

export default function RapportSeoAutomatiquePage() {
  return (
    <SeoLanding
      trail="Rapport SEO automatique"
      badge="Rapport d'audit partageable, gratuit"
      badgeIcon={FileText}
      h1="Rapport SEO automatique : ce qu'il doit contenir, et ce qu'il faut en retirer"
      lede="La plupart des rapports SEO sont longs, flatteurs et sans conséquence. Un rapport utile tient sur une page, date chaque chiffre, nomme sa source, et se termine par ce qu'on fait ensuite."
      ctaPrimary={{ href: "/audit", label: "Générer un rapport gratuit" }}
      ctaSecondary={{ href: "/tools", label: "Voir les outils gratuits" }}
      benefitsTitle="Les règles d'un rapport sur lequel on peut décider"
      benefits={BENEFITS}
      faqTitle="Questions fréquentes sur le rapport SEO automatique"
      faq={FAQ}
      finalCtaTitle="Produisez-en un maintenant, sans compte"
      finalCtaText="L'audit gratuit produit un rapport daté et partageable par lien : erreurs techniques, priorités, et ce qui bloque l'indexation. Aucune inscription, et le lien s'ouvre sur un téléphone."
      finalCtaPrimary={{ href: "/audit", label: "Générer mon rapport" }}
      finalCtaSecondary={{ href: "/login", label: "Ouvrir un compte" }}
      jsonLd={serviceJsonLd}
    >
      <h2>Pourquoi les rapports SEO ne sont pas lus</h2>
      <p>
        Le rapport type fait trente à quarante pages, s&apos;ouvre sur un score global,
        enchaîne des graphiques exportés d&apos;outils tiers, et se termine sur des
        recommandations génériques. Il coûte des heures à produire, il rassure au moment de
        l&apos;envoi, et personne ne l&apos;ouvre au deuxième mois.
      </p>
      <p>
        La raison est simple : il ne répond à aucune question que le destinataire se pose.
        Un dirigeant de PME veut savoir trois choses. Est-ce que ça avance. Qu&apos;est-ce
        qui a été fait avec l&apos;argent. Qu&apos;est-ce qui bloque. Un document qui met
        ces réponses en page trente ne sera jamais lu jusque-là.
      </p>
      <p>
        Le format qui fonctionne est court par conception, pas court par paresse. Tout ce
        qui n&apos;influence aucune décision sort, y compris quand c&apos;est joli et que
        ça a demandé du travail.
      </p>

      <h2>Les quatre blocs qui suffisent</h2>
      <p>
        <strong>Ce qui a bougé.</strong> Les positions qui montent et celles qui
        descendent, avec l&apos;ampleur du mouvement et la date de la mesure. Sans la
        date, un chiffre se lit comme s&apos;il datait d&apos;aujourd&apos;hui, ce qui fait
        prendre des décisions sur du passé.
      </p>
      <p>
        <strong>Ce qui a été fait.</strong> Les pages publiées, les corrections
        appliquées, les redirections posées. C&apos;est le bloc qui relie la dépense au
        travail, et c&apos;est aussi celui que les rapports d&apos;agence omettent le plus
        souvent, parce qu&apos;il est le plus vérifiable.
      </p>
      <p>
        <strong>Ce qui bloque.</strong> Les problèmes techniques qui empêchent le reste de
        produire un effet : pages non indexables, liens morts, redirections en chaîne.
        Court, ordonné par conséquence réelle, pas par nombre d&apos;occurrences.
      </p>
      <p>
        <strong>Ce qui suit.</strong> Deux ou trois actions nommées pour la période
        suivante. Un rapport qui ne se termine pas par une décision est un bulletin, pas un
        outil de pilotage.
      </p>

      <h2>La règle qui change tout : dater et nommer la source</h2>
      <p>
        Un chiffre sans date ni source n&apos;est pas une donnée, c&apos;est une
        affirmation. Et les sources d&apos;un rapport SEO ne mesurent pas la même chose.
        Search Console rapporte ce que Google a enregistré, avec deux à trois jours de
        décalage et un échantillonnage sur les longues périodes. Un relevé de position
        interroge une page de résultats à un instant précis, depuis une localisation
        précise. Une exploration décrit l&apos;état du site au moment du passage.
      </p>
      <p>
        Les trois sont justes et ne se contredisent pas : elles répondent à des questions
        différentes. Un rapport honnête indique laquelle il utilise pour chaque chiffre,
        parce que la conclusion à en tirer n&apos;est pas la même. Un écart entre deux
        sources n&apos;est pas une erreur, c&apos;est une information.
      </p>

      <h2>Le mode d&apos;échec silencieux, et comment l&apos;éviter</h2>
      <p>
        Le plus grand danger d&apos;un rapport automatique n&apos;est pas qu&apos;il se
        trompe bruyamment, c&apos;est qu&apos;il se trompe en silence. Une source qui
        répond mal, un quota dépassé, un délai d&apos;attente atteint : si le code affiche
        zéro plutôt que d&apos;expliquer, le lecteur voit un effondrement là où il n&apos;y
        a qu&apos;une panne technique. Les réactions qui suivent coûtent parfois plus cher
        que le problème réel.
      </p>
      <p>
        La règle appliquée dans Gridar est l&apos;inverse : quand une mesure échoue, le
        rapport affiche la raison et laisse la case vide. C&apos;est moins élégant sur une
        capture d&apos;écran et c&apos;est la seule façon de garder un document sur lequel
        on peut décider. Un tableau de bord complet mais faux est pire qu&apos;un tableau
        de bord troué et honnête.
      </p>

      <h2>Pourquoi le score global unique ne sert à rien</h2>
      <p>
        Un score sur cent rassure parce qu&apos;il donne une direction en un coup
        d&apos;oeil. Il additionne pourtant des éléments sans commune mesure : une balise
        de titre trop longue et une page bloquée à l&apos;indexation entrent dans le même
        calcul, alors que la première coûte quelques clics et la seconde coûte la page
        entière.
      </p>
      <p>
        Le remplacement utile est une courte liste ordonnée par conséquence, avec la
        correction attendue pour chaque ligne. Trois problèmes réglés valent mieux
        qu&apos;un score passé de 62 à 71 sans qu&apos;on sache pourquoi.
      </p>

      <h2>Un lien plutôt qu&apos;une pièce jointe</h2>
      <p>
        Le PDF envoyé par courriel se périme à la seconde où il part, se perd dans une
        boîte de réception et s&apos;ouvre mal sur un téléphone. Un lien reste à jour à
        chaque ouverture, se consulte partout, et s&apos;imprime en PDF quand le contexte
        l&apos;exige, sans qu&apos;il faille maintenir deux versions.
      </p>
      <p>
        L&apos;<Link href="/audit">audit gratuit</Link> produit exactement ce format : un
        rapport daté, partageable par un lien à jeton, sans inscription pour la personne
        qui le reçoit. Pour suivre l&apos;évolution entre deux rapports, le{" "}
        <Link href="/suivi-position-google-canada">suivi de position</Link> donne le rang
        réel sur Google.ca ville par ville, et la page{" "}
        <Link href="/logiciel-referencement-automatique">logiciel de référencement</Link>{" "}
        détaille ce qui s&apos;automatise entre deux rapports.
      </p>
    </SeoLanding>
  );
}
