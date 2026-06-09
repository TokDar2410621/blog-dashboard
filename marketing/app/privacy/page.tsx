import type { Metadata } from "next";
import Link from "next/link";
import { MarketingHeader } from "@/components/MarketingHeader";
import { MarketingFooter } from "@/components/MarketingFooter";

export const metadata: Metadata = {
  title: "Politique de confidentialité",
  description:
    "Comment Gridar collecte, utilise et protège tes données. Conforme à la Loi 25 du Québec et au RGPD.",
  alternates: { canonical: "/privacy" },
  robots: { index: true, follow: true },
};

export default function Privacy() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <MarketingHeader trail="Confidentialité" />

      {/* Top emerald wash, same hero recipe as landing. */}
      <div className="fixed inset-x-0 top-0 h-[40vh] z-0 pointer-events-none bg-gradient-to-b from-emerald-500/[0.04] via-transparent to-transparent" />

      <main className="relative z-10 max-w-3xl mx-auto px-4 md:px-6 py-12">
        <article
          className="prose prose-invert max-w-none
                     prose-headings:text-zinc-100 prose-headings:tracking-tight
                     prose-h1:text-4xl prose-h1:font-bold
                     prose-h2:mt-12 prose-h2:border-t prose-h2:border-white/10 prose-h2:pt-8 prose-h2:text-2xl
                     prose-h3:text-xl prose-h3:text-zinc-100
                     prose-p:text-zinc-300 prose-li:text-zinc-300
                     prose-strong:text-zinc-100
                     prose-a:text-emerald-400 prose-a:no-underline hover:prose-a:text-emerald-300 hover:prose-a:underline
                     prose-code:before:content-none prose-code:after:content-none
                     prose-code:bg-zinc-900 prose-code:border prose-code:border-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[0.9em] prose-code:font-mono prose-code:text-emerald-300
                     prose-table:text-sm
                     prose-th:bg-white/5 prose-th:font-semibold prose-th:text-zinc-100 prose-th:border-white/10
                     prose-td:border-white/10 prose-td:text-zinc-300
                     prose-hr:border-white/10"
        >
          <h1>Politique de confidentialité</h1>
          <p className="text-sm text-zinc-500">
            Dernière mise à jour : 9 mai 2026. S&apos;applique à <strong>gridar.app</strong> et tous les services exposés à <code>api.gridar.app</code>.
          </p>

          <h2>1. Qui sommes-nous</h2>
          <p>
            Gridar est un produit opéré par <strong>Arivex Studio</strong>, basée
            au Québec, Canada. Pour toute question relative à tes données :
          </p>
          <ul>
            <li>Courriel : <a href="mailto:tokamdarius@gmail.com">tokamdarius@gmail.com</a></li>
            <li>Personne responsable de la protection des renseignements personnels : Darius Tokam, fondateur</li>
          </ul>

          <h2>2. Quelles données on collecte</h2>
          <h3>Données de compte</h3>
          <ul>
            <li>Adresse courriel et nom d&apos;utilisateur</li>
            <li>Mot de passe (stocké uniquement sous forme de hash bcrypt, jamais en clair)</li>
            <li>Plan d&apos;abonnement et statut de paiement</li>
            <li>Identifiants OAuth Google ou GitHub (si connexion sociale utilisée)</li>
          </ul>

          <h3>Données de tes sites et contenus</h3>
          <ul>
            <li>Domaine, langue, configuration EEAT/Branding/Knowledge base que tu fournis</li>
            <li>Articles que tu génères ou édites dans Gridar</li>
            <li>Mots-clés trackés et historique de positions Google</li>
            <li>Identifiants de connexion à ton CMS (WordPress Application Password, Shopify Admin Token, Webflow Site Token), chiffrés au repos</li>
            <li>Refresh token Google Search Console si tu connectes GSC, chiffré, révocable à tout moment</li>
          </ul>

          <h3>Données de facturation</h3>
          <p>
            Le traitement des paiements est délégué à <strong>Stripe</strong>. Gridar
            ne stocke <em>jamais</em> tes informations de carte de crédit. On
            conserve uniquement l&apos;identifiant client Stripe, ton plan et l&apos;historique
            des factures.
          </p>

          <h3>Données techniques</h3>
          <ul>
            <li>Adresse IP, navigateur, système d&apos;exploitation (logs serveur, conservés 30 jours)</li>
            <li>Cookies de session pour maintenir ta connexion</li>
            <li>Aucun outil de tracking publicitaire tiers (Google Analytics, Facebook Pixel, etc.) sur l&apos;application</li>
          </ul>

          <h2>3. Comment on utilise tes données</h2>
          <ul>
            <li><strong>Fournir le service</strong> : générer des articles, auditer ton SEO, suivre tes positions, publier sur ton CMS</li>
            <li><strong>Facturer ton plan</strong> via Stripe</li>
            <li><strong>Communiquer avec toi</strong> : alertes par courriel (rapport hebdo, déclin de trafic, quota approchant). Tu peux désactiver chaque alerte individuellement</li>
            <li><strong>Améliorer le produit</strong> : analyse agrégée et anonymisée de l&apos;usage</li>
          </ul>
          <p>
            <strong>On ne vend jamais tes données.</strong> On ne fait pas de
            partage à des fins marketing avec des tiers.
          </p>

          <h2>4. Sous-traitants</h2>
          <p>
            Gridar s&apos;appuie sur les services suivants pour fonctionner. Chacun
            applique sa propre politique de confidentialité :
          </p>
          <table>
            <thead>
              <tr>
                <th>Sous-traitant</th>
                <th>Rôle</th>
                <th>Données concernées</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noopener noreferrer">Anthropic (Claude)</a></td>
                <td>Génération de texte par IA</td>
                <td>Sujets, mots-clés, contenu en cours de rédaction</td>
              </tr>
              <tr>
                <td><a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google (Gemini, Search Console, PageSpeed)</a></td>
                <td>IA secondaire, OAuth GSC, Core Web Vitals</td>
                <td>Texte des articles, URL de tes sites, refresh token GSC</td>
              </tr>
              <tr>
                <td><a href="https://serper.dev/privacy" target="_blank" rel="noopener noreferrer">Serper</a></td>
                <td>Recherches SERP, mots-clés, compétiteurs</td>
                <td>Mots-clés, URL, géolocalisation (Québec par défaut)</td>
              </tr>
              <tr>
                <td><a href="https://stripe.com/en-ca/privacy" target="_blank" rel="noopener noreferrer">Stripe</a></td>
                <td>Paiements, abonnements, factures</td>
                <td>Courriel, nom, infos de carte (jamais vues par Gridar)</td>
              </tr>
              <tr>
                <td><a href="https://vercel.com/legal/privacy-policy" target="_blank" rel="noopener noreferrer">Vercel</a></td>
                <td>Hébergement de l&apos;interface gridar.app</td>
                <td>Logs d&apos;accès</td>
              </tr>
              <tr>
                <td><a href="https://railway.app/legal/privacy" target="_blank" rel="noopener noreferrer">Railway</a></td>
                <td>Hébergement du backend api.gridar.app</td>
                <td>Logs serveur, données applicatives</td>
              </tr>
              <tr>
                <td><a href="https://www.pexels.com/privacy-policy/" target="_blank" rel="noopener noreferrer">Pexels</a></td>
                <td>Banque d&apos;images de couverture</td>
                <td>Mots-clés de recherche d&apos;images</td>
              </tr>
            </tbody>
          </table>
          <p>
            Certains de ces sous-traitants peuvent traiter tes données aux
            États-Unis ou dans d&apos;autres juridictions. En utilisant Gridar, tu
            acceptes ce transfert. Aucune donnée n&apos;est revendue à des tiers
            non listés ici.
          </p>

          <h2>5. Conservation des données</h2>
          <ul>
            <li><strong>Compte actif</strong> : conservé tant que ton compte existe</li>
            <li><strong>Articles et configurations</strong> : conservés tant que ton site est actif</li>
            <li><strong>Logs serveur</strong> : 30 jours</li>
            <li><strong>Données de facturation</strong> : 7 ans (obligation fiscale canadienne)</li>
            <li><strong>Compte supprimé</strong> : effacement complet sous 30 jours, sauf données de facturation (obligation légale)</li>
          </ul>

          <h2>6. Tes droits (Loi 25 et RGPD)</h2>
          <p>
            En tant que résident du Québec ou de l&apos;Union européenne, tu disposes
            des droits suivants :
          </p>
          <ul>
            <li><strong>Accès</strong> : demander une copie de toutes tes données</li>
            <li><strong>Rectification</strong> : corriger toute donnée inexacte</li>
            <li><strong>Suppression (droit à l&apos;oubli)</strong> : supprimer ton compte et toutes les données associées</li>
            <li><strong>Portabilité</strong> : exporter tes articles dans un format ouvert (Markdown, JSON)</li>
            <li><strong>Opposition</strong> : t&apos;opposer au traitement à des fins d&apos;amélioration produit</li>
            <li><strong>Retrait du consentement</strong> : à tout moment, sans justification</li>
          </ul>
          <p>
            Pour exercer un de ces droits, écris à <a href="mailto:tokamdarius@gmail.com">tokamdarius@gmail.com</a>.
            On te répond sous 30 jours maximum.
          </p>
          <p>
            Tu peux aussi déposer une plainte auprès de la <a href="https://www.cai.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">Commission d&apos;accès à l&apos;information du Québec</a>.
          </p>

          <h2>7. Cookies</h2>
          <p>
            Gridar utilise un nombre minimal de cookies, tous strictement
            nécessaires :
          </p>
          <ul>
            <li><code>access_token</code> et <code>refresh_token</code> : maintien de ta session JWT</li>
            <li><code>i18nextLng</code> : mémorise ta langue préférée (FR/EN/ES)</li>
          </ul>
          <p>
            Aucun cookie publicitaire ou de pistage tiers. Aucun cookie tiers
            chargé tant que tu n&apos;es pas connecté.
          </p>

          <h2>8. Sécurité</h2>
          <ul>
            <li>HTTPS obligatoire sur tout le service (HSTS, max-age 2 ans)</li>
            <li>Mots de passe hashés (bcrypt)</li>
            <li>Tokens API et secrets CMS chiffrés au repos</li>
            <li>Backups quotidiens, conservés 7 jours</li>
            <li>Aucune donnée stockée sur disque local non chiffré</li>
            <li>Accès admin restreint à Darius Tokam, authentifié par 2FA</li>
          </ul>
          <p>
            En cas de violation de données affectant tes renseignements
            personnels, on te notifie sous 72 heures par courriel.
          </p>

          <h2>9. Mineurs</h2>
          <p>
            Gridar n&apos;est pas destiné aux personnes de moins de 18 ans. Si tu es
            mineur et que tu as créé un compte, contacte-nous pour le supprimer.
          </p>

          <h2>10. Modifications de cette politique</h2>
          <p>
            On peut mettre à jour cette politique pour refléter des changements
            dans nos pratiques ou la loi. La date en haut est toujours actualisée.
            Pour les changements substantiels, on te notifie par courriel au moins
            15 jours avant l&apos;entrée en vigueur.
          </p>

          <h2>11. Contact</h2>
          <p>
            Pour toute question, demande d&apos;exercice de droit ou plainte :
          </p>
          <ul>
            <li><strong>Courriel</strong> : <a href="mailto:tokamdarius@gmail.com">tokamdarius@gmail.com</a></li>
            <li><strong>Responsable</strong> : Darius Tokam, fondateur d&apos;Arivex Studio</li>
          </ul>

          <hr />
          <p className="text-sm text-zinc-500">
            Voir aussi : <Link href="/terms">Conditions d&apos;utilisation</Link>.
          </p>
        </article>
      </main>

      <MarketingFooter />
    </div>
  );
}
