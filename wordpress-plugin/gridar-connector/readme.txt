=== Gridar Connector ===
Contributors: arivexstudio
Tags: seo, ai, content, automation, audit
Requires at least: 5.6
Tested up to: 6.7
Requires PHP: 7.4
Stable tag: 1.0.0
License: MIT
License URI: https://opensource.org/licenses/MIT

Connecte ton WordPress a Gridar (gridar.app) en 1 click pour generer des articles SEO en francais quebecois, auditer ton site et suivre tes positions sur Google.

== Description ==

Gridar est un SaaS d'audit SEO + generation d'articles IA, optimise pour le marche francophone (Quebec en priorite). Ce plugin elimine le pas-a-pas manuel habituel (creer un Application Password dans Utilisateurs > Profil, le copier, aller dans Gridar, coller, valider) en faisant tout en 1 click.

Apres installation :

1. Va sur gridar.app/account/api-keys et genere un token.
2. Reglages > Gridar dans ton admin WP.
3. Colle le token, clique Connecter.

Le plugin genere automatiquement une Application Password (visible dans Utilisateurs > Profil > Application Passwords sous le nom "Gridar Connector") et l'envoie chiffree (HTTPS) a Gridar. Aucun copier-coller a faire de ton cote.

Tu peux revoquer la connexion a tout moment depuis la meme page admin.

== Installation ==

1. Telecharge le plugin depuis le repertoire WordPress.org ou upload le ZIP dans Extensions > Ajouter.
2. Active le plugin.
3. Reglages > Gridar.

== Frequently Asked Questions ==

= Mes credentials WordPress sont-elles partagees avec Gridar ? =

Non. Le plugin genere une Application Password (un mot de passe dedie aux apps externes), pas ton mot de passe principal. Tu peux la revoquer a tout moment.

= Le plugin envoie quoi exactement a Gridar ? =

L'URL de ton site, ton nom d'utilisateur WordPress, et l'Application Password generee. Le tout via HTTPS. Aucun contenu d'article n'est envoye lors de la connexion.

= Comment je revoque la connexion ? =

Reglages > Gridar > "Deconnecter ce site". Ou Utilisateurs > Profil > Application Passwords, supprime "Gridar Connector".

== Changelog ==

= 1.0.0 =
- Premiere release : connexion 1-click + revocation propre.
