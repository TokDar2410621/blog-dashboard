import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";

export const metadata: Metadata = {
  title: "Conditions d'utilisation",
  description:
    "Conditions d'utilisation de Gridar (Arivex Studio). Inscription, plans, propriete intellectuelle, limitations de responsabilite, droit applicable.",
  alternates: { canonical: "/terms" },
  robots: { index: true, follow: true },
};

export default function Terms() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border/50 bg-background/95 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="sm" className="-ml-2">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Accueil
            </Button>
          </Link>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-2">
            <GridarMark className="h-5 w-5" />
            <span className="font-semibold">Gridar</span>
            <span className="text-muted-foreground hidden sm:inline">/ Conditions</span>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 md:px-6 py-10">
        <article
          className="prose prose-zinc dark:prose-invert max-w-none
                     prose-h1:text-3xl prose-h1:font-bold
                     prose-h2:mt-10 prose-h2:border-t prose-h2:border-border/40 prose-h2:pt-6
                     prose-a:text-primary prose-a:no-underline hover:prose-a:underline"
        >
          <h1>Conditions d&apos;utilisation</h1>
          <p className="text-sm text-muted-foreground">
            Derniere mise a jour : 9 mai 2026
          </p>

          <p>
            En utilisant <strong>gridar.app</strong> ou <code>api.gridar.app</code>,
            tu acceptes ces conditions. Lis-les attentivement. Si tu n&apos;es pas
            d&apos;accord, n&apos;utilise pas le service.
          </p>

          <h2>1. Identite de l&apos;entreprise</h2>
          <p>
            Gridar est un produit opere par <strong>Arivex Studio</strong>,
            une entreprise basee au Quebec, Canada. Quand on dit &quot;on&quot;, &quot;nous&quot;,
            &quot;Gridar&quot; dans ce document, on designe Arivex Studio agissant sous
            la marque Gridar.
          </p>

          <h2>2. Service offert</h2>
          <p>
            Gridar est une plateforme SaaS qui automatise la creation, l&apos;audit
            et la publication de contenu SEO pour les sites web. Le service
            comprend notamment :
          </p>
          <ul>
            <li>Generation d&apos;articles par intelligence artificielle</li>
            <li>Audit SEO et suggestions d&apos;optimisation</li>
            <li>Recherche de mots-cles et suivi de positions Google</li>
            <li>Publication automatique sur WordPress, Shopify, Webflow ou un blog heberge</li>
            <li>Detection de declin de contenu, broken links, opportunites de maillage interne</li>
            <li>API publique, serveur MCP, node n8n communautaire</li>
          </ul>
          <p>
            On peut ajouter, modifier ou retirer des fonctionnalites a tout
            moment. Les changements majeurs sont annonces dans le <Link href="/docs/changelog">changelog</Link>.
          </p>

          <h2>3. Compte et acces</h2>
          <ul>
            <li>Tu dois avoir au moins 18 ans pour creer un compte</li>
            <li>Tu fournis des informations exactes lors de l&apos;inscription</li>
            <li>Tu es responsable de la confidentialite de ton mot de passe et de tes tokens API</li>
            <li>Un seul compte par personne ou entreprise. Pas de comptes multiples pour contourner les quotas.</li>
            <li>Tu nous notifies immediatement si tu suspectes un acces non autorise a ton compte</li>
          </ul>

          <h2>4. Plans, prix et facturation</h2>
          <h3>Plans</h3>
          <p>Les plans et leurs limites sont decrits sur la <a href="/#pricing">page des tarifs</a>. Au moment de la redaction :</p>
          <ul>
            <li><strong>Essai gratuit</strong> : 1 site, 1 article par mois, fonctionnalites limitees</li>
            <li><strong>Solo</strong> : 29,99 $ CAD/mois</li>
            <li><strong>Pro</strong> : 89,99 $ CAD/mois</li>
            <li><strong>Agence</strong> : 199,99 $ CAD/mois</li>
            <li><strong>Credits one-shot</strong> : 25/99/299 $ CAD pour 10/50/200 articles supplementaires</li>
          </ul>
          <p>
            Tous les prix sont en dollars canadiens, taxes en sus. Les prix
            peuvent evoluer ; les abonnes actuels sont notifies au moins 30
            jours avant tout changement.
          </p>

          <h3>Cycle de facturation</h3>
          <ul>
            <li>Abonnement renouvele automatiquement chaque mois</li>
            <li>Facturation effectuee par <strong>Stripe</strong> a la date anniversaire de ton inscription</li>
            <li>Credits achetes : factures une seule fois, n&apos;expirent pas, reportes mois sur mois</li>
            <li>Echec de paiement : 3 tentatives sur 7 jours. Compte mis en pause si le paiement echoue toujours</li>
          </ul>

          <h3>Annulation et remboursement</h3>
          <ul>
            <li>Tu peux annuler ton abonnement a tout moment depuis ton dashboard</li>
            <li>L&apos;annulation prend effet a la fin du cycle de facturation en cours (pas de remboursement au prorata)</li>
            <li>Tes articles restent accessibles tant que ton compte existe ou jusqu&apos;a 30 jours apres suppression</li>
            <li>Pas de remboursement apres le premier mois de service utilise. Premier mois remboursable sous 14 jours sur demande motivee.</li>
          </ul>

          <h2>5. Quotas et utilisation acceptable</h2>
          <p>
            Chaque plan a des limites (sites, articles/mois, mots-cles trackes,
            requetes API/heure). Le depassement peut entrainer :
          </p>
          <ul>
            <li>Blocage temporaire du service concerne jusqu&apos;au prochain cycle</li>
            <li>Possibilite d&apos;acheter des credits ou de passer a un plan superieur</li>
          </ul>
          <p>Tu t&apos;engages a <strong>ne pas</strong> utiliser Gridar pour :</p>
          <ul>
            <li>Generer du contenu illegal, diffamatoire, haineux, sexuellement explicite ou trompeur</li>
            <li>Creer du spam, des fermes de contenu (content farms) ou du contenu genere en masse sans valeur editoriale</li>
            <li>Usurper l&apos;identite d&apos;une autre personne ou entreprise</li>
            <li>Contourner ou tenter de contourner les quotas (multi-comptes, scripts d&apos;evasion)</li>
            <li>Faire du reverse engineering du service ou attaquer notre infrastructure</li>
            <li>Revendre l&apos;acces au service a des tiers sans autorisation ecrite (sauf via le plan Agence qui inclut le multi-client)</li>
          </ul>
          <p>
            On se reserve le droit de suspendre ou resilier ton compte sans
            preavis en cas de violation, avec remboursement au prorata du mois
            en cours si la suspension est de notre fait sans faute prouvee.
          </p>

          <h2>6. Propriete intellectuelle</h2>
          <h3>Ton contenu</h3>
          <p>
            <strong>Tu es proprietaire</strong> du contenu que tu generes ou
            edites dans Gridar (articles, briefs, configurations). On obtient
            uniquement la licence non-exclusive minimale necessaire pour
            heberger, traiter et te livrer ton contenu.
          </p>
          <p>
            <strong>Important, contenu IA</strong> : les articles generes par
            l&apos;IA sont produits a partir de tes inputs (sujet, mots-cles, brief,
            knowledge base). La legislation sur le droit d&apos;auteur applique au
            contenu genere par IA evolue ; selon les juridictions, tu peux ne
            pas pouvoir revendiquer un droit d&apos;auteur exclusif sur certaines
            productions purement IA. Pour autant que la loi le permette, tu
            obtiens tous les droits transmissibles sur le contenu genere.
          </p>

          <h3>Notre service</h3>
          <p>
            La marque Gridar, le logo, le code source, les algorithmes
            proprietaires (incluant nos prompts IA), la documentation et
            l&apos;interface utilisateur restent la propriete exclusive d&apos;Arivex
            Studio. Aucun droit ne t&apos;est cede sur ces elements.
          </p>

          <h3>Open source et tiers</h3>
          <p>
            Le serveur MCP <code>@gridar/mcp-server</code> et le node n8n
            <code>n8n-nodes-gridar</code> sont publies sous licence MIT. Tu peux
            les modifier et redistribuer selon les termes de cette licence.
          </p>

          <h2>7. Responsabilites de l&apos;utilisateur</h2>
          <ul>
            <li>Tu garantis avoir les droits de pousser du contenu sur les sites tiers que tu connectes (ton WordPress, Shopify, etc.)</li>
            <li>Tu verifies l&apos;exactitude factuelle du contenu IA avant publication. <strong>L&apos;IA peut halluciner.</strong></li>
            <li>Tu respectes les conditions d&apos;utilisation de tes plateformes tierces (WordPress, Shopify, Webflow, Google, etc.)</li>
            <li>Tu respectes le droit d&apos;auteur des contenus que tu utilises comme references ou knowledge base</li>
            <li>Tu es seul responsable des consequences SEO ou editoriales de la publication de tes articles</li>
          </ul>

          <h2>8. Limitation de responsabilite</h2>
          <p>
            Gridar est fourni <strong>&quot;tel quel&quot;</strong> sans garantie d&apos;aucune
            sorte. Dans la limite maximale autorisee par le droit quebecois et
            canadien :
          </p>
          <ul>
            <li>On ne garantit pas que le service soit exempt d&apos;erreurs, ininterrompu ou exempt de bugs</li>
            <li>On ne garantit aucun resultat SEO precis (positions Google, trafic, conversions). Le SEO depend de centaines de facteurs hors de notre controle.</li>
            <li>On n&apos;est pas responsable des decisions editoriales prises sur la base de contenu genere par notre IA</li>
            <li>On n&apos;est pas responsable des dommages indirects, perte de profits, perte de donnees, perte de classement Google</li>
            <li>Notre responsabilite totale, toutes causes confondues, est plafonnee au montant que tu as effectivement paye pour le service au cours des 12 derniers mois</li>
          </ul>

          <h2>9. Indemnisation</h2>
          <p>
            Tu acceptes d&apos;indemniser et defendre Arivex Studio contre toute
            reclamation tierce resultant de :
          </p>
          <ul>
            <li>Ton utilisation du service en violation des presentes conditions</li>
            <li>Ton contenu (articles, knowledge base, etc.)</li>
            <li>Ta violation des droits d&apos;un tiers (droit d&apos;auteur, marque, vie privee)</li>
          </ul>

          <h2>10. Resiliation</h2>
          <ul>
            <li><strong>Par toi</strong> : a tout moment depuis ton compte. Annulation prend effet en fin de cycle de facturation.</li>
            <li><strong>Par nous</strong> : avec preavis de 30 jours par courriel pour cause non-faute, ou immediatement en cas de violation grave des presentes conditions</li>
            <li><strong>Effet de la resiliation</strong> : acces au service revoque, articles conserves 30 jours puis effaces, donnees de facturation conservees selon obligations legales</li>
          </ul>
          <p>
            Tu peux exporter tes articles dans un format ouvert (Markdown, JSON)
            avant suppression du compte.
          </p>

          <h2>11. Modifications du service et des conditions</h2>
          <p>
            On peut modifier ces conditions a tout moment. Pour les
            modifications substantielles, tu es notifie par courriel au moins
            15 jours avant l&apos;entree en vigueur. Continuer a utiliser Gridar
            apres cette date constitue une acceptation des nouvelles conditions.
            Si tu n&apos;es pas d&apos;accord, tu peux annuler ton compte avant l&apos;entree
            en vigueur.
          </p>

          <h2>12. Force majeure</h2>
          <p>
            On n&apos;est pas responsable des defaillances dues a des evenements
            hors de notre controle raisonnable : panne d&apos;un fournisseur tiers
            (Anthropic, Google, Stripe, Vercel, Railway), catastrophe naturelle,
            cyberattaque, panne d&apos;Internet, action gouvernementale.
          </p>

          <h2>13. Loi applicable et juridiction</h2>
          <p>
            Ces conditions sont regies par les lois en vigueur dans la
            <strong> province de Quebec, Canada</strong>, sans egard aux conflits
            de lois. Tout litige sera tranche par les tribunaux competents du
            district de Saint-Hyacinthe, Quebec, Canada, sauf si la loi sur
            la protection du consommateur du Quebec t&apos;accorde un droit plus
            favorable.
          </p>

          <h2>14. Divers</h2>
          <ul>
            <li><strong>Integralite de l&apos;accord</strong> : ces conditions, completees par notre <Link href="/privacy">politique de confidentialite</Link>, constituent l&apos;integralite de l&apos;accord entre toi et nous</li>
            <li><strong>Divisibilite</strong> : si une clause est jugee invalide, le reste reste en vigueur</li>
            <li><strong>Renonciation</strong> : le fait qu&apos;on n&apos;applique pas une clause a un moment donne ne vaut pas renonciation a l&apos;appliquer plus tard</li>
            <li><strong>Cession</strong> : on peut ceder ces conditions en cas de fusion ou acquisition d&apos;Arivex Studio. Tu ne peux pas les ceder a un tiers sans notre accord.</li>
          </ul>

          <h2>15. Contact</h2>
          <p>
            Toute question, demande d&apos;eclaircissement ou notification legale :
          </p>
          <ul>
            <li><strong>Courriel</strong> : <a href="mailto:tokamdarius@gmail.com">tokamdarius@gmail.com</a></li>
            <li><strong>Personne</strong> : Darius Tokam, fondateur d&apos;Arivex Studio, Saint-Hyacinthe, QC</li>
          </ul>

          <hr />
          <p className="text-sm text-muted-foreground">
            Voir aussi : <Link href="/privacy">Politique de confidentialite</Link>.
          </p>
        </article>
      </main>
    </div>
  );
}
