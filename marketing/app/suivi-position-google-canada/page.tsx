import type { Metadata } from "next";
import Link from "next/link";
import { MarketingHeader } from "@/components/MarketingHeader";
import { MarketingFooter } from "@/components/MarketingFooter";
import { PositionCheckTool } from "@/components/PositionCheckTool";
import { Button } from "@/components/ui/button";
import {
  MapPin,
  Gift,
  Zap,
  Globe,
  CalendarClock,
  ArrowRight,
} from "lucide-react";

const PAGE_URL = "https://www.gridar.app/suivi-position-google-canada";

export const metadata: Metadata = {
  title: { absolute: "Suivi position Google Canada gratuit | Gridar" },
  description:
    "Verifie tes positions Google.ca en temps reel, gratuitement, geolocalise par ville quebecoise. Suivi position Google Canada, resultat en 30 secondes.",
  alternates: { canonical: PAGE_URL },
  openGraph: {
    title: "Suivi position Google Canada gratuit et geolocalise au Quebec",
    description:
      "Entre ton URL, ton mot-cle et ta ville quebecoise : recois ton rang exact sur Google.ca en 30 secondes. Gratuit, sans inscription.",
    url: PAGE_URL,
    type: "website",
    siteName: "Gridar",
    locale: "fr_CA",
  },
  robots: { index: true, follow: true },
};

// FAQ source de verite : sert a la fois a la section visible et au JSON-LD FAQPage.
const FAQ_ITEMS: { question: string; answer: string }[] = [
  {
    question: "Comment verifier ma position sur Google au Canada ?",
    answer:
      "Entre ton adresse web, ton mot-cle et ta ville quebecoise dans l'outil plus haut, puis clique sur Verifier. On interroge Google.ca geolocalise a ta ville et on te renvoie ton rang exact en une trentaine de secondes. Aucune inscription requise, et tu vois aussi le top 3 qui occupe les premieres places.",
  },
  {
    question: "Pourquoi ma position change selon la ville ?",
    answer:
      "Google personnalise ses resultats selon la proximite. Une entreprise pres de la personne qui cherche a plus de chances d'apparaitre en tete. On peut donc etre premier a Montreal et absent a Quebec pour le meme mot-cle. Un suivi credible doit toujours preciser la ville, sinon la donnee ne veut rien dire.",
  },
  {
    question: "C'est vraiment gratuit ?",
    answer:
      "Oui. Le check ponctuel de position est 100% gratuit et ne demande ni courriel ni carte de credit. Tu peux l'utiliser autant de fois que tu veux. Le suivi automatique quotidien, lui, fait partie de l'abonnement Gridar, mais rien ne t'oblige a passer a la version payante pour un check ponctuel.",
  },
  {
    question: "Quelle est la difference entre Google.ca et Google.com ?",
    answer:
      "Google.ca est la version canadienne : elle privilegie les resultats pertinents au Canada et en francais pour le Quebec. Google.com penche vers un contexte americain et anglophone. Ta clientele quebecoise cherche presque toujours sur Google.ca, donc c'est le bon domaine a suivre. Notre outil interroge Google.ca par defaut.",
  },
  {
    question: "A quelle frequence devrais-je verifier mes positions ?",
    answer:
      "Un check ponctuel de temps en temps te donne une idee, mais les positions bougent chaque jour. Pour reagir vite quand une page decroche, un suivi quotidien automatique est ideal. Si tu le fais a la main, une verification par semaine au minimum est un bon depart.",
  },
  {
    question:
      "Est-ce que Semrush ou Ahrefs geolocalisent au niveau de la ville au Quebec ?",
    answer:
      "Rarement, et jamais avec la finesse d'un outil concu pour le marche quebecois. Ces plateformes internationales suivent surtout au niveau du pays et sous-estiment le volume de recherche en francais quebecois. Gridar a ete bati pour le Quebec d'abord, avec une geolocalisation par ville quebecoise.",
  },
];

const BENEFITS: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  text: string;
}[] = [
  {
    icon: MapPin,
    title: "Geolocalise par ville QC",
    text: "Choisis Montreal, Quebec, Gatineau ou Saguenay et obtiens le rang exact a cet endroit, pas une moyenne nationale floue.",
  },
  {
    icon: Gift,
    title: "Gratuit, sans inscription",
    text: "Aucun courriel, aucune carte de credit. Entre ton URL et ton mot-cle, tu as ta position tout de suite.",
  },
  {
    icon: Zap,
    title: "En temps reel",
    text: "On interroge Google.ca au moment ou tu cliques. Le rang affiche est celui d'aujourd'hui, pas une donnee vieille de trois semaines.",
  },
  {
    icon: Globe,
    title: "Specifique a Google.ca",
    text: "Pays regle sur le Canada, langue francaise. Tu vois ce que ta clientele quebecoise voit vraiment quand elle cherche.",
  },
  {
    icon: CalendarClock,
    title: "Suivi quotidien automatise",
    text: "Passe du check ponctuel au suivi automatique : un instantane par jour, des alertes des qu'une page decroche.",
  },
];

const serviceJsonLd = {
  "@context": "https://schema.org",
  "@type": "Service",
  name: "Suivi de position Google Canada",
  description:
    "Verification et suivi des positions sur Google.ca, geolocalise par ville quebecoise, pour les PME du Quebec. Check ponctuel gratuit et suivi quotidien automatique.",
  url: PAGE_URL,
  serviceType: "Suivi de positionnement SEO local",
  provider: {
    "@type": "Organization",
    name: "Gridar",
    url: "https://www.gridar.app",
  },
  areaServed: {
    "@type": "AdministrativeArea",
    name: "Quebec, Canada",
  },
};

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQ_ITEMS.map((item) => ({
    "@type": "Question",
    name: item.question,
    acceptedAnswer: {
      "@type": "Answer",
      text: item.answer,
    },
  })),
};

export default function SuiviPositionGoogleCanadaPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd) }}
      />

      <MarketingHeader trail="Suivi position Google" />

      {/* Emerald wash, meme recette que le hero de la landing. */}
      <div className="fixed inset-x-0 top-0 h-[45vh] z-0 pointer-events-none bg-gradient-to-b from-emerald-500/[0.06] via-transparent to-transparent" />

      <main className="relative z-10">
        {/* 1. HERO */}
        <section className="max-w-4xl mx-auto px-4 md:px-6 pt-14 pb-8 text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/[0.06] px-3 py-1 text-xs text-emerald-300">
            <MapPin className="h-3.5 w-3.5" />
            Outil gratuit, geolocalise au Quebec
          </span>
          <h1 className="mt-5 text-3xl md:text-5xl font-bold tracking-tight text-zinc-50">
            Suivi position Google Canada : verifie ton rang Google.ca gratuitement
          </h1>
          <p className="mt-5 text-lg md:text-xl text-zinc-300 max-w-2xl mx-auto">
            Verifiez vos positions Google.ca en temps reel, 100% gratuit,
            resultats geolocalises Quebec en 30 secondes.
          </p>
          <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
            <Button
              asChild
              size="lg"
              className="bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold"
            >
              <a href="#outil">
                Verifier ma position maintenant
                <ArrowRight className="h-4 w-4 ml-2" />
              </a>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="border-white/15 text-zinc-200 hover:bg-white/5"
            >
              <Link href="/audit">Faire un audit SEO complet</Link>
            </Button>
          </div>
        </section>

        {/* 2. L'OUTIL interactif */}
        <section id="outil" className="scroll-mt-24 px-4 md:px-6 pb-4">
          <PositionCheckTool />
        </section>

        {/* 3. BENEFICES */}
        <section className="max-w-5xl mx-auto px-4 md:px-6 py-16">
          <h2 className="text-center text-2xl md:text-3xl font-bold text-zinc-50 mb-10">
            Le seul verificateur de rang pense pour le Quebec
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {BENEFITS.map((b) => {
              const Icon = b.icon;
              return (
                <div
                  key={b.title}
                  className="rounded-xl border border-white/10 bg-white/[0.02] p-5"
                >
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 mb-3">
                    <Icon className="h-5 w-5 text-emerald-400" />
                  </div>
                  <h3 className="font-semibold text-zinc-100 mb-1.5">
                    {b.title}
                  </h3>
                  <p className="text-sm text-zinc-400 leading-relaxed">
                    {b.text}
                  </p>
                </div>
              );
            })}
          </div>
        </section>

        {/* 4. CONTENU */}
        <section className="max-w-3xl mx-auto px-4 md:px-6 pb-16">
          <article
            className="prose prose-invert max-w-none
                       prose-headings:text-zinc-100 prose-headings:tracking-tight
                       prose-h2:mt-12 prose-h2:border-t prose-h2:border-white/10 prose-h2:pt-8 prose-h2:text-2xl
                       prose-h3:text-xl prose-h3:text-zinc-100
                       prose-p:text-zinc-300 prose-li:text-zinc-300
                       prose-strong:text-zinc-100
                       prose-a:text-emerald-400 prose-a:no-underline hover:prose-a:text-emerald-300 hover:prose-a:underline"
          >
            <h2>Pourquoi ta position Google.ca varie selon la ville au Quebec</h2>
            <p>
              Google ne montre pas les memes resultats a une personne a Montreal
              et a une personne a Saguenay, meme pour un mot-cle identique. Depuis
              que la recherche locale s&apos;est generalisee, le moteur tient
              compte de l&apos;endroit ou tu te trouves pour classer les commerces,
              les services et meme les articles de blogue a saveur regionale. Un
              plombier de Laval peut troner en premiere position chez lui et
              disparaitre completement des resultats a Levis.
            </p>
            <p>
              Cette variation vient du local pack, ces trois fiches avec une carte
              qui apparaissent en haut de plusieurs recherches, et du signal de
              proximite que Google applique aux resultats organiques. Plus ton
              entreprise est pres de la personne qui cherche, plus tu as de chances
              de ranker. C&apos;est une excellente nouvelle pour une PME
              quebecoise : tu n&apos;as pas a battre le Canada au complet, juste ta
              ville et ta region.
            </p>
            <p>
              C&apos;est aussi pour ca qu&apos;un suivi de position credible doit
              etre geolocalise. Verifier ton rang sans preciser la ville te donne
              une moyenne floue qui ne correspond a la realite d&apos;aucun de tes
              clients. Notre outil te laisse choisir Montreal, Quebec, Gatineau,
              Laval, Longueuil, Sherbrooke, Trois-Rivieres ou Saguenay, et te
              renvoie le classement reel a cet endroit precis.
            </p>

            <h2>
              Suivi position Google Canada : comment lire Google.ca plutot que
              Google.com
            </h2>
            <p>
              Beaucoup d&apos;outils te montrent tes positions sur google.com, la
              version americaine. Le probleme, c&apos;est que ta clientele
              quebecoise, elle, tape ses recherches sur Google.ca, souvent en
              francais, souvent depuis un appareil mobile situe au Quebec. Les deux
              pages de resultats ne sont pas identiques : le domaine, la langue et
              le pays changent le classement.
            </p>
            <p>
              Un bon suivi interroge Google avec les bons parametres : pays regle
              sur le Canada, langue francaise et une localisation a l&apos;echelle
              de la ville. C&apos;est exactement ce que fait notre outil en
              arriere-plan. Le rang que tu vois correspond a ce qu&apos;un vrai
              client verrait en cherchant depuis ta ville, pas a une moyenne
              mondiale ni a un resultat americain.
            </p>
            <p>
              Lire la bonne page de resultats change tout quand vient le temps de
              decider ou investir tes efforts. Un article qui plafonne en page deux
              sur Google.com peut deja etre dans le top 5 sur Google.ca a
              Trois-Rivieres. Sans la bonne lentille, tu passes a cote de tes vraies
              victoires.
            </p>

            <h2>Pourquoi les outils generiques ratent le local quebecois</h2>
            <p>
              Semrush, Ahrefs et compagnie sont des outils remarquables, mais ils
              ont ete concus pour un marche international. Leur suivi de position
              fonctionne surtout au niveau du pays, parfois de la region, rarement
              de la ville, et presque jamais avec la finesse necessaire pour
              distinguer un quartier de Montreal d&apos;une banlieue de la
              Rive-Sud. Leurs bases de donnees de mots-cles sous-estiment aussi le
              volume de recherche en francais quebecois, ce qui fausse tes
              priorites.
            </p>
            <p>
              Resultat : tu paies cher un abonnement mensuel en dollars americains
              pour des donnees qui ne refletent pas ton marche reel. Pour un
              dentiste de Sherbrooke ou un garagiste de Terrebonne, savoir
              qu&apos;on rank quelque part au Canada ne vaut rien. Ce qui compte,
              c&apos;est le rang exact dans la ville d&apos;ou viennent les clients
              qui poussent la porte.
            </p>
            <p>
              Gridar part de l&apos;inverse. On a bati un outil pour le Quebec
              d&apos;abord : lexique FR-CA, geolocalisation par ville quebecoise et
              lecture de Google.ca par defaut. C&apos;est la difference entre un
              tableau de bord qui te flatte et un tableau de bord qui te dit la
              verite sur ton marche local.
            </p>

            <h2>Comment Gridar fait le suivi position Google Canada au quotidien</h2>
            <p>
              Le check gratuit sur cette page, c&apos;est la version ponctuelle :
              une photo de ta position aujourd&apos;hui. Utile, mais une position
              isolee ne dit pas si tu montes ou si tu recules. Pour ca, il faut
              mesurer chaque jour et regarder la tendance.
            </p>
            <p>
              Le suivi automatique de Gridar prend un instantane de tes mots-cles
              chaque jour, ville par ville, sur Google.ca. Tu vois ta courbe
              evoluer, tu recois une alerte quand une page decroche et tu
              identifies les articles qui perdent du terrain avant qu&apos;ils
              disparaissent des resultats. Branche ta Google Search Console et on
              croise tes vraies impressions avec tes rangs pour prioriser les pages
              a retravailler.
            </p>
            <p>
              Concretement : tu commences gratuitement avec le check ponctuel
              ci-dessus, puis tu passes au suivi quotidien quand tu veux garder
              l&apos;oeil sur plusieurs mots-cles et plusieurs villes sans lever le
              petit doigt. C&apos;est le meme moteur, geolocalise au Quebec, mais en
              continu. Tu peux aussi lancer un{" "}
              <Link href="/audit">audit SEO complet gratuit</Link> pour voir tout ce
              qui joue sur tes positions.
            </p>
          </article>
        </section>

        {/* 5. FAQ */}
        <section className="max-w-3xl mx-auto px-4 md:px-6 pb-16">
          <h2 className="text-2xl md:text-3xl font-bold text-zinc-50 mb-8 text-center">
            Questions frequentes sur le suivi position Google Canada
          </h2>
          <div className="space-y-3">
            {FAQ_ITEMS.map((item) => (
              <details
                key={item.question}
                className="group rounded-xl border border-white/10 bg-white/[0.02] p-5"
              >
                <summary className="cursor-pointer list-none font-semibold text-zinc-100 flex items-center justify-between gap-4">
                  {item.question}
                  <span className="text-emerald-400 transition-transform group-open:rotate-45 text-xl leading-none">
                    +
                  </span>
                </summary>
                <p className="mt-3 text-sm text-zinc-400 leading-relaxed">
                  {item.answer}
                </p>
              </details>
            ))}
          </div>
        </section>

        {/* 6. CTA FINAL */}
        <section className="max-w-3xl mx-auto px-4 md:px-6 pb-20">
          <div className="rounded-2xl border border-emerald-500/30 bg-gradient-to-b from-emerald-500/[0.08] to-transparent p-8 md:p-10 text-center">
            <h2 className="text-2xl md:text-3xl font-bold text-zinc-50">
              Prends le controle de ton suivi position Google Canada
            </h2>
            <p className="mt-4 text-zinc-300 max-w-xl mx-auto">
              Commence par un audit SEO complet gratuit, puis active le suivi
              quotidien automatique de tes positions Google.ca, ville par ville.
              Concu et opere au Quebec.
            </p>
            <div className="mt-7 flex flex-col sm:flex-row gap-3 justify-center">
              <Button
                asChild
                size="lg"
                className="bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold"
              >
                <Link href="/audit">
                  Audit SEO complet gratuit
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="outline"
                className="border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 hover:text-emerald-200"
              >
                <Link href="/login">Essayer le suivi quotidien automatique</Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <MarketingFooter />
    </div>
  );
}
