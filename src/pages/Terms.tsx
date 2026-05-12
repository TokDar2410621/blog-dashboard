/**
 * Conditions d'utilisation Gridar.
 *
 * IMPORTANT: ceci est un point de départ. Faire réviser par un avocat
 * avant le launch public, surtout les sections "propriété intellectuelle"
 * (contenu IA-généré) et "limitation de responsabilité".
 */
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";

export default function Terms() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border/50 bg-background/95 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="-ml-2"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Accueil
          </Button>
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
          <h1>Conditions d'utilisation</h1>
          <p className="text-sm text-muted-foreground">
            Dernière mise à jour : 9 mai 2026
          </p>

          <p>
            En utilisant <strong>gridar.app</strong> ou <code>api.gridar.app</code>,
            tu acceptes ces conditions. Lis-les attentivement. Si tu n'es pas
            d'accord, n'utilise pas le service.
          </p>

          <h2>1. Identité de l'entreprise</h2>
          <p>
            Gridar est un produit opéré par <strong>Arivex Studio</strong>,
            une entreprise basée au Québec, Canada. Quand on dit "on", "nous",
            "Gridar" dans ce document, on désigne Arivex Studio agissant sous
            la marque Gridar.
          </p>

          <h2>2. Service offert</h2>
          <p>
            Gridar est une plateforme SaaS qui automatise la création, l'audit
            et la publication de contenu SEO pour les sites web. Le service
            comprend notamment :
          </p>
          <ul>
            <li>Génération d'articles par intelligence artificielle</li>
            <li>Audit SEO et suggestions d'optimisation</li>
            <li>Recherche de mots-clés et suivi de positions Google</li>
            <li>Publication automatique sur WordPress, Shopify, Webflow ou un blog hébergé</li>
            <li>Détection de déclin de contenu, broken links, opportunités de maillage interne</li>
            <li>API publique, serveur MCP, node n8n communautaire</li>
          </ul>
          <p>
            On peut ajouter, modifier ou retirer des fonctionnalités à tout
            moment. Les changements majeurs sont annoncés dans le <Link to="/docs/changelog">changelog</Link>.
          </p>

          <h2>3. Compte et accès</h2>
          <ul>
            <li>Tu dois avoir au moins 18 ans pour créer un compte</li>
            <li>Tu fournis des informations exactes lors de l'inscription</li>
            <li>Tu es responsable de la confidentialité de ton mot de passe et de tes tokens API</li>
            <li>Un seul compte par personne ou entreprise - pas de comptes multiples pour contourner les quotas</li>
            <li>Tu nous notifies immédiatement si tu suspectes un accès non autorisé à ton compte</li>
          </ul>

          <h2>4. Plans, prix et facturation</h2>
          <h3>Plans</h3>
          <p>Les plans et leurs limites sont décrits sur la <a href="/#pricing">page des tarifs</a> et dans <Link to="/docs/plans-credits">la documentation</Link>. Au moment de la rédaction :</p>
          <ul>
            <li><strong>Essai gratuit</strong> : 1 site, 1 article par mois, fonctionnalités limitées</li>
            <li><strong>Solo</strong> : 29,99 $ CAD/mois</li>
            <li><strong>Pro</strong> : 89,99 $ CAD/mois</li>
            <li><strong>Agence</strong> : 199,99 $ CAD/mois</li>
            <li><strong>Crédits one-shot</strong> : 25/99/299 $ CAD pour 10/50/200 articles supplémentaires</li>
          </ul>
          <p>
            Tous les prix sont en dollars canadiens, taxes en sus. Les prix
            peuvent évoluer ; les abonnés actuels sont notifiés au moins 30
            jours avant tout changement.
          </p>

          <h3>Cycle de facturation</h3>
          <ul>
            <li>Abonnement renouvelé automatiquement chaque mois</li>
            <li>Facturation effectuée par <strong>Stripe</strong> à la date anniversaire de ton inscription</li>
            <li>Crédits achetés : facturés une seule fois, n'expirent pas, reportés mois sur mois</li>
            <li>Échec de paiement : 3 tentatives sur 7 jours. Compte mis en pause si le paiement échoue toujours</li>
          </ul>

          <h3>Annulation et remboursement</h3>
          <ul>
            <li>Tu peux annuler ton abonnement à tout moment depuis <Link to="/billing">/billing</Link></li>
            <li>L'annulation prend effet à la fin du cycle de facturation en cours (pas de remboursement au prorata)</li>
            <li>Tes articles restent accessibles tant que ton compte existe ou jusqu'à 30 jours après suppression</li>
            <li>Pas de remboursement après le premier mois de service utilisé. Premier mois remboursable sous 14 jours sur demande motivée</li>
          </ul>

          <h2>5. Quotas et utilisation acceptable</h2>
          <p>
            Chaque plan a des limites (sites, articles/mois, mots-clés trackés,
            requêtes API/heure). Le dépassement peut entraîner :
          </p>
          <ul>
            <li>Blocage temporaire du service concerné jusqu'au prochain cycle</li>
            <li>Possibilité d'acheter des crédits ou de passer à un plan supérieur</li>
          </ul>
          <p>Tu t'engages à <strong>ne pas</strong> utiliser Gridar pour :</p>
          <ul>
            <li>Générer du contenu illégal, diffamatoire, haineux, sexuellement explicite ou trompeur</li>
            <li>Créer du spam, des fermes de contenu (content farms) ou du contenu généré en masse sans valeur éditoriale</li>
            <li>Usurper l'identité d'une autre personne ou entreprise</li>
            <li>Contourner ou tenter de contourner les quotas (multi-comptes, scripts d'évasion)</li>
            <li>Faire du reverse engineering du service ou attaquer notre infrastructure</li>
            <li>Revendre l'accès au service à des tiers sans autorisation écrite (sauf via le plan Agence qui inclut le multi-client)</li>
          </ul>
          <p>
            On se réserve le droit de suspendre ou résilier ton compte sans
            préavis en cas de violation, avec remboursement au prorata du mois
            en cours si la suspension est de notre fait sans faute prouvée.
          </p>

          <h2>6. Propriété intellectuelle</h2>
          <h3>Ton contenu</h3>
          <p>
            <strong>Tu es propriétaire</strong> du contenu que tu génères ou
            édites dans Gridar (articles, briefs, configurations). On obtient
            uniquement la licence non-exclusive minimale nécessaire pour
            héberger, traiter et te livrer ton contenu.
          </p>
          <p>
            <strong>Important - contenu IA</strong> : les articles générés par
            l'IA sont produits à partir de tes inputs (sujet, mots-clés, brief,
            knowledge base). La législation sur le droit d'auteur appliqué au
            contenu généré par IA évolue ; selon les juridictions, tu peux ne
            pas pouvoir revendiquer un droit d'auteur exclusif sur certaines
            productions purement IA. Pour autant que la loi le permette, tu
            obtiens tous les droits transmissibles sur le contenu généré.
          </p>

          <h3>Notre service</h3>
          <p>
            La marque Gridar, le logo, le code source, les algorithmes
            propriétaires (incluant nos prompts IA), la documentation et
            l'interface utilisateur restent la propriété exclusive d'Arivex
            Studio. Aucun droit ne t'est cédé sur ces éléments.
          </p>

          <h3>Open source et tiers</h3>
          <p>
            Le serveur MCP <code>@gridar/mcp-server</code> et le node n8n
            <code>n8n-nodes-gridar</code> sont publiés sous licence MIT. Tu peux
            les modifier et redistribuer selon les termes de cette licence.
          </p>

          <h2>7. Responsabilités de l'utilisateur</h2>
          <ul>
            <li>Tu garantis avoir les droits de pousser du contenu sur les sites tiers que tu connectes (ton WordPress, Shopify, etc.)</li>
            <li>Tu vérifies l'exactitude factuelle du contenu IA avant publication. <strong>L'IA peut halluciner.</strong></li>
            <li>Tu respectes les conditions d'utilisation de tes plateformes tierces (WordPress, Shopify, Webflow, Google, etc.)</li>
            <li>Tu respectes le droit d'auteur des contenus que tu utilises comme références ou knowledge base</li>
            <li>Tu es seul responsable des conséquences SEO ou éditoriales de la publication de tes articles</li>
          </ul>

          <h2>8. Limitation de responsabilité</h2>
          <p>
            Gridar est fourni <strong>"tel quel"</strong> sans garantie d'aucune
            sorte. Dans la limite maximale autorisée par le droit québécois et
            canadien :
          </p>
          <ul>
            <li>On ne garantit pas que le service soit exempt d'erreurs, ininterrompu ou exempt de bugs</li>
            <li>On ne garantit aucun résultat SEO précis (positions Google, trafic, conversions). Le SEO dépend de centaines de facteurs hors de notre contrôle</li>
            <li>On n'est pas responsable des décisions éditoriales prises sur la base de contenu généré par notre IA</li>
            <li>On n'est pas responsable des dommages indirects, perte de profits, perte de données, perte de classement Google</li>
            <li>Notre responsabilité totale, toutes causes confondues, est plafonnée au montant que tu as effectivement payé pour le service au cours des 12 derniers mois</li>
          </ul>

          <h2>9. Indemnisation</h2>
          <p>
            Tu acceptes d'indemniser et défendre Arivex Studio contre toute
            réclamation tierce résultant de :
          </p>
          <ul>
            <li>Ton utilisation du service en violation des présentes conditions</li>
            <li>Ton contenu (articles, knowledge base, etc.)</li>
            <li>Ta violation des droits d'un tiers (droit d'auteur, marque, vie privée)</li>
          </ul>

          <h2>10. Résiliation</h2>
          <ul>
            <li><strong>Par toi</strong> : à tout moment depuis ton compte. Annulation prend effet en fin de cycle de facturation</li>
            <li><strong>Par nous</strong> : avec préavis de 30 jours par courriel pour cause non-faute, ou immédiatement en cas de violation grave des présentes conditions</li>
            <li><strong>Effet de la résiliation</strong> : accès au service révoqué, articles conservés 30 jours puis effacés, données de facturation conservées selon obligations légales</li>
          </ul>
          <p>
            Tu peux exporter tes articles dans un format ouvert (Markdown, JSON)
            avant suppression du compte.
          </p>

          <h2>11. Modifications du service et des conditions</h2>
          <p>
            On peut modifier ces conditions à tout moment. Pour les
            modifications substantielles, tu es notifié par courriel au moins
            15 jours avant l'entrée en vigueur. Continuer à utiliser Gridar
            après cette date constitue une acceptation des nouvelles conditions.
            Si tu n'es pas d'accord, tu peux annuler ton compte avant l'entrée
            en vigueur.
          </p>

          <h2>12. Force majeure</h2>
          <p>
            On n'est pas responsable des défaillances dues à des événements
            hors de notre contrôle raisonnable : panne d'un fournisseur tiers
            (Anthropic, Google, Stripe, Vercel, Railway), catastrophe naturelle,
            cyberattaque, panne d'Internet, action gouvernementale.
          </p>

          <h2>13. Loi applicable et juridiction</h2>
          <p>
            Ces conditions sont régies par les lois en vigueur dans la
            <strong> province de Québec, Canada</strong>, sans égard aux conflits
            de lois. Tout litige sera tranché par les tribunaux compétents du
            district de Saint-Hyacinthe, Québec, Canada - sauf si la loi sur
            la protection du consommateur du Québec t'accorde un droit plus
            favorable.
          </p>

          <h2>14. Divers</h2>
          <ul>
            <li><strong>Intégralité de l'accord</strong> : ces conditions, complétées par notre <Link to="/privacy">politique de confidentialité</Link>, constituent l'intégralité de l'accord entre toi et nous</li>
            <li><strong>Divisibilité</strong> : si une clause est jugée invalide, le reste reste en vigueur</li>
            <li><strong>Renonciation</strong> : le fait qu'on n'applique pas une clause à un moment donné ne vaut pas renonciation à l'appliquer plus tard</li>
            <li><strong>Cession</strong> : on peut céder ces conditions en cas de fusion ou acquisition d'Arivex Studio. Tu ne peux pas les céder à un tiers sans notre accord</li>
          </ul>

          <h2>15. Contact</h2>
          <p>
            Toute question, demande d'éclaircissement ou notification légale :
          </p>
          <ul>
            <li><strong>Courriel</strong> : <a href="mailto:tokamdarius@gmail.com">tokamdarius@gmail.com</a></li>
            <li><strong>Personne</strong> : Darius Tokam, fondateur d'Arivex Studio, Saint-Hyacinthe, QC</li>
          </ul>

          <hr />
          <p className="text-sm text-muted-foreground">
            Voir aussi : <Link to="/privacy">Politique de confidentialité</Link>.
          </p>
        </article>
      </main>
    </div>
  );
}
