# Connecter WordPress

Pour les sites WordPress 5.6+. Aucun plugin requis - on utilise l'**Application Passwords** natif de WordPress.

## Pré-requis

- WordPress 5.6 ou plus récent
- Accès admin au site (un compte avec rôle Administrator)
- L'API REST WordPress doit être accessible publiquement à `tonsite.ca/wp-json/` (c'est le défaut, sauf si bloqué par un plugin de sécurité)

## Étapes

### 1. Génère un Application Password dans WordPress

1. Connecte-toi à `tonsite.ca/wp-admin`
2. Profil (en haut à droite) → scroll jusqu'à **Application Passwords**
3. Donne un nom : `Gridar`
4. Clique **Add New Application Password**
5. WordPress te montre un mot de passe au format `xxxx xxxx xxxx xxxx xxxx xxxx`
6. **Copie-le immédiatement** - il ne sera plus affiché

> Tu ne vois pas la section ? Vérifie que tu es en HTTPS (ou ajoute `define('WP_ENVIRONMENT_TYPE', 'local');` dans `wp-config.php` si tu es en HTTP local). Application Passwords est désactivé en HTTP par défaut depuis WP 5.6.

### 2. Connecte dans Gridar

Sites → **Connecter WordPress**. Tu remplis :

- **URL du site** : `https://tonsite.ca` (sans `/wp-admin`, sans slash final)
- **Username** : ton login WP (pas l'email - le slug du compte)
- **Application Password** : la chaîne avec espaces (copie-colle directement, on enlève les espaces)

### 3. Ce qu'on fait sous le capot

1. `GET tonsite.ca/wp-json/` → on confirme que c'est bien WordPress avec REST API active
2. `GET tonsite.ca/wp-json/wp/v2/users/me` avec ton Application Password → on confirme l'authentification
3. Scan branding sur `tonsite.ca` → couleur, logo, fonts pré-remplis
4. Création de la `Site` row, redirection vers son dashboard

Si tout passe : confetti emerald + tu arrives au dashboard.

### 4. Comportement après publication

Quand tu génères un article via Gridar, on `POST` vers `tonsite.ca/wp-json/wp/v2/posts` avec :
- Titre, slug, contenu (HTML rendu depuis Markdown)
- Statut `publish` par défaut
- Excerpt
- Tags / catégories si tu les fournis

L'article apparaît immédiatement sur **ton site** à l'URL définie par ton permalink WordPress (généralement `tonsite.ca/2026/05/article-slug/`).

## Limites du mode WordPress

- **Pas d'images cover automatiques** : le `featured_media` exige un upload séparé en deux étapes (upload media → set as featured). On ne le fait pas pour l'instant. Pour un cover, ajoute une image dans le contenu Markdown.
- **Lexique FR-CA appliqué au contenu** mais pas aux catégories/tags WordPress (qui restent ce que tu as déjà).
- **Polylang / WPML** : non supporté - on publie en une seule langue par site. Si tu as un setup multilingue avancé, crée un site Gridar par langue.

## Dépannage

| Erreur | Cause | Fix |
|---|---|---|
| "Identifiants WordPress invalides" | Mauvais username ou password | Re-vérifie le username (slug, pas email). Re-génère un Application Password. |
| "Site WordPress non détecté" | REST API désactivée | Ton hébergeur ou un plugin de sécurité bloque `/wp-json/`. Demande à ton hébergeur d'autoriser l'API REST. |
| "Site injoignable" | Erreur DNS ou HTTP 5xx | URL mal écrite ou ton site est down. Teste `curl https://tonsite.ca/wp-json/` dans un terminal. |
| Article publié mais 404 | Permalinks pas flushés | WordPress Admin → Réglages → Permalinks → cliquer "Save" (sans rien changer) flush la rewrite table. |
