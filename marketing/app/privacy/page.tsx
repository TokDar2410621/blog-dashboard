import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";

export const metadata: Metadata = {
  title: "Politique de confidentialite",
  description:
    "Comment Gridar collecte, utilise et protege tes donnees. Conforme a la Loi 25 du Quebec et au RGPD.",
  alternates: { canonical: "/privacy" },
  robots: { index: true, follow: true },
};

export default function Privacy() {
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
            <span className="text-muted-foreground hidden sm:inline">/ Confidentialite</span>
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
          <h1>Politique de confidentialite</h1>
          <p className="text-sm text-muted-foreground">
            Derniere mise a jour : 9 mai 2026. S'applique a <strong>gridar.app</strong> et tous les services exposes a <code>api.gridar.app</code>.
          </p>

          <h2>1. Qui sommes-nous</h2>
          <p>
            Gridar est un produit opere par <strong>Arivex Studio</strong>, basee
            au Quebec, Canada. Pour toute question relative a tes donnees :
          </p>
          <ul>
            <li>Courriel : <a href="mailto:tokamdarius@gmail.com">tokamdarius@gmail.com</a></li>
            <li>Personne responsable de la protection des renseignements personnels : Darius Tokam, fondateur</li>
          </ul>

          <h2>2. Quelles donnees on collecte</h2>
          <h3>Donnees de compte</h3>
          <ul>
            <li>Adresse courriel et nom d'utilisateur</li>
            <li>Mot de passe (stocke uniquement sous forme de hash bcrypt, jamais en clair)</li>
            <li>Plan d'abonnement et statut de paiement</li>
            <li>Identifiants OAuth Google ou GitHub (si connexion sociale utilisee)</li>
          </ul>

          <h3>Donnees de tes sites et contenus</h3>
          <ul>
            <li>Domaine, langue, configuration EEAT/Branding/Knowledge base que tu fournis</li>
            <li>Articles que tu generes ou edites dans Gridar</li>
            <li>Mots-cles trackes et historique de positions Google</li>
            <li>Identifiants de connexion a ton CMS (WordPress Application Password, Shopify Admin Token, Webflow Site Token), chiffres au repos</li>
            <li>Refresh token Google Search Console si tu connectes GSC, chiffre, revocable a tout moment</li>
          </ul>

          <h3>Donnees de facturation</h3>
          <p>
            Le traitement des paiements est delegue a <strong>Stripe</strong>. Gridar
            ne stocke <em>jamais</em> tes informations de carte de credit. On
            conserve uniquement l'identifiant client Stripe, ton plan et l'historique
            des factures.
          </p>

          <h3>Donnees techniques</h3>
          <ul>
            <li>Adresse IP, navigateur, systeme d'exploitation (logs serveur, conserves 30 jours)</li>
            <li>Cookies de session pour maintenir ta connexion</li>
            <li>Aucun outil de tracking publicitaire tiers (Google Analytics, Facebook Pixel, etc.) sur l'application</li>
          </ul>

          <h2>3. Comment on utilise tes donnees</h2>
          <ul>
            <li><strong>Fournir le service</strong> : generer des articles, auditer ton SEO, suivre tes positions, publier sur ton CMS</li>
            <li><strong>Facturer ton plan</strong> via Stripe</li>
            <li><strong>Communiquer avec toi</strong> : alertes par courriel (rapport hebdo, declin de trafic, quota approchant). Tu peux desactiver chaque alerte individuellement</li>
            <li><strong>Ameliorer le produit</strong> : analyse agregee et anonymisee de l'usage</li>
          </ul>
          <p>
            <strong>On ne vend jamais tes donnees.</strong> On ne fait pas de
            partage a des fins marketing avec des tiers.
          </p>

          <h2>4. Sous-traitants</h2>
          <p>
            Gridar s'appuie sur les services suivants pour fonctionner. Chacun
            applique sa propre politique de confidentialite :
          </p>
          <table>
            <thead>
              <tr>
                <th>Sous-traitant</th>
                <th>Role</th>
                <th>Donnees concernees</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><a href="https://www.anthropic.com/legal/privacy" target="_blank" rel="noopener noreferrer">Anthropic (Claude)</a></td>
                <td>Generation de texte par IA</td>
                <td>Sujets, mots-cles, contenu en cours de redaction</td>
              </tr>
              <tr>
                <td><a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">Google (Gemini, Search Console, PageSpeed)</a></td>
                <td>IA secondaire, OAuth GSC, Core Web Vitals</td>
                <td>Texte des articles, URL de tes sites, refresh token GSC</td>
              </tr>
              <tr>
                <td><a href="https://serper.dev/privacy" target="_blank" rel="noopener noreferrer">Serper</a></td>
                <td>Recherches SERP, mots-cles, competiteurs</td>
                <td>Mots-cles, URL, geolocalisation (Quebec par defaut)</td>
              </tr>
              <tr>
                <td><a href="https://stripe.com/en-ca/privacy" target="_blank" rel="noopener noreferrer">Stripe</a></td>
                <td>Paiements, abonnements, factures</td>
                <td>Courriel, nom, infos de carte (jamais vues par Gridar)</td>
              </tr>
              <tr>
                <td><a href="https://vercel.com/legal/privacy-policy" target="_blank" rel="noopener noreferrer">Vercel</a></td>
                <td>Hebergement de l'interface gridar.app</td>
                <td>Logs d'acces</td>
              </tr>
              <tr>
                <td><a href="https://railway.app/legal/privacy" target="_blank" rel="noopener noreferrer">Railway</a></td>
                <td>Hebergement du backend api.gridar.app</td>
                <td>Logs serveur, donnees applicatives</td>
              </tr>
              <tr>
                <td><a href="https://www.pexels.com/privacy-policy/" target="_blank" rel="noopener noreferrer">Pexels</a></td>
                <td>Banque d'images de couverture</td>
                <td>Mots-cles de recherche d'images</td>
              </tr>
            </tbody>
          </table>
          <p>
            Certains de ces sous-traitants peuvent traiter tes donnees aux
            Etats-Unis ou dans d'autres juridictions. En utilisant Gridar, tu
            acceptes ce transfert. Aucune donnee n'est revendue a des tiers
            non listes ici.
          </p>

          <h2>5. Conservation des donnees</h2>
          <ul>
            <li><strong>Compte actif</strong> : conserve tant que ton compte existe</li>
            <li><strong>Articles et configurations</strong> : conserves tant que ton site est actif</li>
            <li><strong>Logs serveur</strong> : 30 jours</li>
            <li><strong>Donnees de facturation</strong> : 7 ans (obligation fiscale canadienne)</li>
            <li><strong>Compte supprime</strong> : effacement complet sous 30 jours, sauf donnees de facturation (obligation legale)</li>
          </ul>

          <h2>6. Tes droits (Loi 25 et RGPD)</h2>
          <p>
            En tant que resident du Quebec ou de l'Union europeenne, tu disposes
            des droits suivants :
          </p>
          <ul>
            <li><strong>Acces</strong> : demander une copie de toutes tes donnees</li>
            <li><strong>Rectification</strong> : corriger toute donnee inexacte</li>
            <li><strong>Suppression (droit a l'oubli)</strong> : supprimer ton compte et toutes les donnees associees</li>
            <li><strong>Portabilite</strong> : exporter tes articles dans un format ouvert (Markdown, JSON)</li>
            <li><strong>Opposition</strong> : t'opposer au traitement a des fins d'amelioration produit</li>
            <li><strong>Retrait du consentement</strong> : a tout moment, sans justification</li>
          </ul>
          <p>
            Pour exercer un de ces droits, ecris a <a href="mailto:tokamdarius@gmail.com">tokamdarius@gmail.com</a>.
            On te repond sous 30 jours maximum.
          </p>
          <p>
            Tu peux aussi deposer une plainte aupres de la <a href="https://www.cai.gouv.qc.ca/" target="_blank" rel="noopener noreferrer">Commission d'acces a l'information du Quebec</a>.
          </p>

          <h2>7. Cookies</h2>
          <p>
            Gridar utilise un nombre minimal de cookies, tous strictement
            necessaires :
          </p>
          <ul>
            <li><code>access_token</code> et <code>refresh_token</code> : maintien de ta session JWT</li>
            <li><code>i18nextLng</code> : memorise ta langue preferee (FR/EN/ES)</li>
          </ul>
          <p>
            Aucun cookie publicitaire ou de pistage tiers. Aucun cookie tiers
            charge tant que tu n'es pas connecte.
          </p>

          <h2>8. Securite</h2>
          <ul>
            <li>HTTPS obligatoire sur tout le service (HSTS, max-age 2 ans)</li>
            <li>Mots de passe hashes (bcrypt)</li>
            <li>Tokens API et secrets CMS chiffres au repos</li>
            <li>Backups quotidiens, conserves 7 jours</li>
            <li>Aucune donnee stockee sur disque local non chiffre</li>
            <li>Acces admin restreint a Darius Tokam, authentifie par 2FA</li>
          </ul>
          <p>
            En cas de violation de donnees affectant tes renseignements
            personnels, on te notifie sous 72 heures par courriel.
          </p>

          <h2>9. Mineurs</h2>
          <p>
            Gridar n'est pas destine aux personnes de moins de 18 ans. Si tu es
            mineur et que tu as cree un compte, contacte-nous pour le supprimer.
          </p>

          <h2>10. Modifications de cette politique</h2>
          <p>
            On peut mettre a jour cette politique pour refleter des changements
            dans nos pratiques ou la loi. La date en haut est toujours actualisee.
            Pour les changements substantiels, on te notifie par courriel au moins
            15 jours avant l'entree en vigueur.
          </p>

          <h2>11. Contact</h2>
          <p>
            Pour toute question, demande d'exercice de droit ou plainte :
          </p>
          <ul>
            <li><strong>Courriel</strong> : <a href="mailto:tokamdarius@gmail.com">tokamdarius@gmail.com</a></li>
            <li><strong>Responsable</strong> : Darius Tokam, fondateur d'Arivex Studio</li>
          </ul>

          <hr />
          <p className="text-sm text-muted-foreground">
            Voir aussi : <Link href="/terms">Conditions d&apos;utilisation</Link>.
          </p>
        </article>
      </main>
    </div>
  );
}
