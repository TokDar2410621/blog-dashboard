---
title: Hreflang fr-CA + en-CA — le guide pratique pour un site bilingue québécois
slug: hreflang-fr-ca-en-ca-guide-pratique
date: 2026-04-03
author: Darius Tokam
excerpt: 80% des sites québécois bilingues que j'audite ont un hreflang cassé. C'est gratuit à corriger, ça remonte les positions en 3 semaines, et 10 lignes de HTML suffisent.
tags: [hreflang, seo-technique, bilingue]
---

Si ton site sert du contenu en français et en anglais (cas classique pour une PME québécoise qui vise QC + ROC ou QC + USA), tu DOIS avoir des balises `hreflang` correctement configurées. Sinon, Google :

- Affiche ta version EN à un Québécois qui cherche en français
- Affiche ta version FR à un Torontois qui cherche en anglais
- Considère parfois tes 2 versions comme du duplicate content

Voici le guide précis. 10 lignes de HTML, 3 semaines pour voir l'effet.

## Ce que hreflang dit à Google

`hreflang` est un tag HTML qui pointe vers les variantes linguistiques/géographiques d'une page. Format :

```html
<link rel="alternate" hreflang="fr-CA" href="https://tonsite.ca/article" />
<link rel="alternate" hreflang="en-CA" href="https://tonsite.ca/en/article" />
<link rel="alternate" hreflang="x-default" href="https://tonsite.ca/article" />
```

Google lit ces tags et associe les URLs comme étant équivalentes en sens, différentes en langue/géo. Au moment d'afficher le résultat à un utilisateur, il choisit la bonne version selon les signaux de l'utilisateur (IP, settings de langue, cookies Google).

## Les 4 erreurs classiques (et leur fix)

### Erreur 1 : Utiliser `fr` ou `en` sans suffixe pays

```html
<!-- ❌ Mauvais -->
<link rel="alternate" hreflang="fr" href="..." />

<!-- ✅ Bon -->
<link rel="alternate" hreflang="fr-CA" href="..." />
```

Sans pays, Google traite ton "fr" comme un défaut qui peut s'appliquer à France, Belgique, Suisse, etc. Tu perds la spécificité Québec.

### Erreur 2 : Oublier le tag self-referencing

Chaque page DOIT avoir un hreflang qui pointe vers elle-même, en plus de pointer vers ses alternatives. Sinon Google ne sait pas qui est l'original.

```html
<!-- Sur la page FR -->
<link rel="alternate" hreflang="fr-CA" href="https://tonsite.ca/article" />
<link rel="alternate" hreflang="en-CA" href="https://tonsite.ca/en/article" />
```

Sur la page EN, **inverse-le** :

```html
<link rel="alternate" hreflang="en-CA" href="https://tonsite.ca/en/article" />
<link rel="alternate" hreflang="fr-CA" href="https://tonsite.ca/article" />
```

### Erreur 3 : Pages qui ne se référencent pas mutuellement

Si la FR pointe vers la EN, la EN DOIT pointer vers la FR. Sinon Google ignore les tags des deux côtés.

### Erreur 4 : Oublier `x-default`

```html
<link rel="alternate" hreflang="x-default" href="https://tonsite.ca/article" />
```

C'est le fallback que Google utilise pour les utilisateurs dont la langue n'est pas couverte (ex. un Allemand). Pour un site québécois bilingue, mets ton URL française comme `x-default`.

## Où placer les tags

Trois endroits possibles, par préférence :

1. **Dans le `<head>` HTML** (le plus simple, le plus rapide)
2. **Dans le HTTP header** (utile pour les PDF, XML, etc. qui n'ont pas de `<head>`)
3. **Dans le sitemap XML** (pour les très gros sites avec beaucoup de variations)

Pour 95 % des cas PME québécoise : `<head>` HTML.

## Test rapide en 2 minutes

1. Ouvre une de tes pages FR
2. View source (Ctrl+U)
3. Cherche `hreflang`
4. Vérifie :
   - ✅ Au moins 1 tag `fr-CA` self-referencing
   - ✅ Au moins 1 tag `en-CA` ou `en-US` vers la version anglaise
   - ✅ 1 tag `x-default`
5. Ouvre la version EN, fais pareil — les tags doivent être MIROIRS

Si une de ces 5 conditions n'est pas remplie, tu as un problème SEO bilingue.

## Le générateur Gridar (gratuit même en Free)

Donne-nous l'URL de ta page FR + l'URL de ta page EN, on génère les 4 tags exacts à copier-coller dans ton `<head>`. Disponible dans **Site Settings → Outil Schema.org → Hreflang generator**.

Pour un site WordPress, plugin Yoast SEO Premium ou RankMath gère automatiquement les hreflang depuis la traduction. Si tu n'as pas ces plugins, le générateur Gridar te fait le HTML à coller manuellement.

## L'effet typique mesuré

Sur 30 sites que j'ai audités avec hreflang cassé, après correction :

- **Médiane de remontée** : 8 positions sur les requêtes locales en 3 semaines
- **Cas best** : un client qui passait de la 23e à la 4e sur "comptabilité PME Québec" en 17 jours, simplement parce que ses pages FR + EN se référençaient enfin correctement

**Pas de magie, juste du SEO technique correct.**

## Lectures liées

- [Le piège du SEO français](/blog/seo-bilingue-fr-ca-piege)
- [Comment ranker au Québec](/blog/comment-ranker-google-quebec-2026)
- [E-E-A-T pour PME québécoises](/blog/eeat-quebec-pme)
