# Articles multilingues + hreflang

Gridar supporte FR, EN et ES sur le même site. Articles traduits sont liés ensemble (via `translation_group`) et déclarés à Google avec `hreflang` pour servir la bonne version selon la géo de l'utilisateur.

## Activer le multilingue sur ton site

**Site Settings → onglet "Langues"**

1. Coche les langues que tu veux activer : FR / EN / ES
2. Choisis la **langue par défaut** (présélectionnée dans l'éditeur)

Si tu actives plusieurs langues, l'éditeur ajoute un select de langue à chaque article et la `KeywordTracker` permet de tracker des mots-clés différents par langue.

## Workflow : article original puis traduction

### 1. Crée l'article original

Comme d'habitude (génération IA ou manuel). Choisis sa langue (généralement FR pour le marché québécois).

### 2. Génère la traduction

Dans l'article publié → bouton **Traduire**. Choix de la langue cible (EN / ES). On génère :

- Titre traduit + slug réécrit (URL-safe pour la langue cible)
- Excerpt traduit
- Contenu traduit avec respect des liens internes (réécris vers les versions traduites quand elles existent)
- Schema mis à jour (langue dans `inLanguage`)
- `translation_group` partagé entre l'original et la traduction → ils savent qu'ils sont les mêmes

L'article traduit arrive en **statut Brouillon**. Tu le révises rapidement (l'IA peut faire des erreurs sur les noms propres et les références culturelles spécifiques) puis Publié.

### 3. Hreflang automatique

À la publication des deux versions liées par `translation_group`, on injecte dans le `<head>` de chaque page :

```html
<link rel="alternate" hreflang="fr-CA" href="https://tonsite.ca/blog/article-fr">
<link rel="alternate" hreflang="en" href="https://tonsite.ca/blog/article-en">
<link rel="alternate" hreflang="x-default" href="https://tonsite.ca/blog/article-fr">
```

Google sert la version FR aux Canadiens FR, EN aux US/UK/EN-CA, et utilise `x-default` (langue principale) en fallback.

## Validation hreflang

**Sidebar → Hreflang check** (ou `POST /api/hreflang-check/`)

Outil qui crawl tes articles et vérifie :
- Toutes les pages de chaque `translation_group` se réfèrent les unes les autres
- Les codes hreflang sont valides (`fr-CA`, `en`, `es`, etc.)
- Pas de boucle ou de référence vers une page qui n'existe pas
- `x-default` est défini

Score 0-100 + liste des erreurs avec correctifs suggérés.

## Mode Shopify / Webflow / WordPress

| Mode | Hreflang auto |
|---|---|
| Hébergé | ✅ Géré par notre Next.js |
| WordPress | ⚠️ Polylang ou WPML requis. On publie l'article + on n'écrit pas le hreflang. À toi de configurer le plugin. |
| Shopify | ⚠️ Shopify Markets fait le hreflang automatiquement quand tu actives les markets. On publie sans hreflang spécifique. |
| Webflow | ⚠️ Webflow Localization (paid feature). Sans, pas de hreflang multilingue propre. |
| Externe | ✅ Tu contrôles le rendu, le code généré par notre scaffolder inclut le hreflang. |

Si ton CMS ne gère pas le multilingue nativement (WordPress sans Polylang), notre conseil : **un site Gridar par langue**, avec des domaines séparés (`tonsite.ca` pour FR, `tonsite.com` pour EN). Plus simple et meilleur SEO global.

## Lexique FR-CA vs FR-FR

Le **lexique FR-CA** s'applique automatiquement aux articles générés en FR. Si tu cibles le marché français (FR-FR), désactive-le :

Site Settings → Langues → FR → "Use Quebec lexicon" → décoche.

L'article généré utilisera alors les termes France (shopping, week-end, parking) et `inLanguage: fr-FR` dans le schema.

## Tracking des positions multilingues

**Suivi des positions → onglet par langue**

Pour chaque mot-clé tracké, tu choisis la langue. On crawl Google avec :
- `gl=ca&hl=fr` pour FR-CA (Canada français)
- `gl=ca&hl=en` pour EN-CA
- `gl=fr&hl=fr` pour FR-FR
- `gl=us&hl=en` pour EN-US

Tu peux donc tracker le même keyword dans plusieurs langues / pays et voir comment chaque marché te classe.

## Translation API (programmatique)

```bash
curl -X POST -H "Authorization: Bearer btb_xxx" \
  -H "Content-Type: application/json" \
  -d '{"slug": "article-fr-original", "target_language": "en"}' \
  https://api.blog-dashboard.ca/api/v1/sites/12/translate/
```

Réponse : nouveau slug + URL de l'article traduit. Le `translation_group` est lié auto.

> Note : la traduction consomme **1 quota mensuel ou 1 crédit** (comme une génération normale).

## Limites

- **3 langues seulement** : FR, EN, ES. Pas DE, IT, PT, JA, ZH pour l'instant.
- **Pas de traduction simultanée** : tu génères l'original puis traduis. Pas de "génère en 3 langues d'un coup".
- **Pas de re-traduction auto** : si tu modifies l'original, la traduction NE se met PAS à jour. À toi de relancer la traduction si l'écart devient grand.

## Use case : SEO bilingue Québec

Stratégie courante pour PME québécoises :
- 70 % des articles en FR-CA (audience locale)
- 30 % en EN (rayonnement national/US)
- `translation_group` lie les paires
- GSC connectée → on voit les positions dans les 2 langues
- Hreflang propre = Google sert la bonne version selon l'utilisateur

Volume idéal pour Pro (60 articles/mois) :
- ~42 articles FR par mois
- ~18 articles EN par mois (souvent traductions des FR les plus performants)
