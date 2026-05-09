# Générer un article avec l'IA

Le workflow signature de Gridar. Du sujet à l'article publié sur ton domaine en ~90 secondes, avec audit SEO + maillage interne automatiques.

## Le formulaire

Dashboard du site → **Générer un article**. Champs disponibles :

### Champs obligatoires (un des deux)

| Champ | Note |
|---|---|
| **Sujet** | Description libre du sujet. L'IA génère un titre + plan à partir de ça. Ex : "Comment choisir un CRM pour PME au Québec en 2026" |
| **Titre forcé** | Si tu veux un titre exact. L'IA respecte ta phrase verbatim au lieu de la reformuler. |

### Champs optionnels

| Champ | Effet |
|---|---|
| **Mots-clés SEO** | CSV. Injectés dans le prompt + la frontmatter. L'IA les répartit naturellement dans le contenu. Vide = on infère depuis le sujet. |
| **Type d'article** | Guide, Tutoriel, Actualité, Comparaison, Avis, Story, Local. Influence le ton et la structure. |
| **Longueur** | Court (~600 mots), Moyen (~1500), Long (~2500). |
| **Méthode de recherche** | `serper` (Google SERP réelle, défaut) ou `gemini` (Google Search via Gemini). Serper est plus fiable. |
| **Langue** | FR / EN / ES selon ce que tu as activé sur le site. Le lexique FR-CA s'applique uniquement en FR. |
| **Aperçu seulement (dry_run)** | Génère sans publier - tu vois le résultat, tu peux régénérer. **Ne consomme pas de quota mensuel ni de crédit.** |

## Étape recommandée : Brief de contenu

Au-dessus du formulaire de génération, il y a une card **Brief de contenu**. Avant de générer un article, génère d'abord un brief :

- **Mot-clé cible** : ton keyword principal
- **Langue**

Le brief produit :
- **Intent** (informational / transactional / navigational / commercial investigation)
- **Outline** (H2/H3 suggérés, structure logique)
- **Entités** à mentionner (people, places, organizations, concepts)
- **FAQ** (questions PAA Google + réponses courtes)
- **Signaux EEAT** à mettre en avant (expertise, expérience, authorité, trust)

Clique **Appliquer** → le brief se branche dans la génération. L'article qui sort est nettement mieux structuré et déjà aligné sur ton intent SEO.

## Ce qui se passe sous le capot

1. **Quota check** - vérification du quota mensuel (1/8/60/200 selon plan) + fallback sur les crédits achetés
2. **Recherche SERP** - Serper API, top 10 résultats Google sur le sujet
3. **Analyse + sélection** - l'IA pick un angle pertinent (anti-cannibalisation : refuse si trop similaire à un article que tu as déjà publié, > 55 % similarity)
4. **Brief implicite** - si tu n'as pas appliqué un Brief de contenu, l'IA construit un mini-brief interne à la volée
5. **Rédaction Claude** - Claude Sonnet 4.6 avec ton `knowledge_base` + lexique FR-CA + EEAT
6. **Maillage interne** - l'IA insère 2-3 liens vers tes articles existants quand pertinent (anti-orphan)
7. **Audit SEO inline** - score global + checks (titre 60c, méta 155c, structure H1/H2, densité keyword, schema)
8. **Corrections automatiques** - title trop long → tronqué, méta manquante → générée, etc.
9. **Cover image** - Pexels search sur le sujet (ou Serper images si activé)
10. **Publication** - via l'adapter du mode (WP / Shopify / Webflow / hosted / external)
11. **Quota / crédit consommé** (uniquement si pas dry_run)
12. **Vercel deploy hook** déclenché si configuré (pour rebuild Next.js statique)

Total : ~60-120 secondes selon longueur + nombre d'articles existants.

## Spécificités FR-CA

Si tu génères en FR sur un site avec le lexique FR-CA activé, les termes France-spécifiques sont remplacés en live :

| France | Québec |
|---|---|
| shopping | magasiner |
| week-end | fin de semaine |
| parking | stationnement |
| email | courriel |
| smartphone | téléphone intelligent |
| ... 50+ termes | ... |

L'IA voit le lexique dans son prompt système. Bonus : les schémas LocalBusiness et Person sont configurés pour `addressRegion=QC` et conventions OQLF.

## Anti-cannibalisation

Avant chaque génération, on récupère les titres de tes 60 derniers articles publiés. Si le titre proposé par l'IA est > 55 % similaire (token Jaccard) à un article existant, on **refuse** la génération avec un message :

> "Cet article serait trop similaire (78 %) à un article existant : 'Comment choisir un CRM en 2026'. Reformule le sujet ou modifie l'article existant."

Tu peux forcer en utilisant **Titre forcé** (l'IA respecte ton titre exact, anti-cannibalisation skipée).

## Quota et crédits

Chaque génération consomme **1 unité** :
1. Si tu as encore du quota mensuel → consommé en quota (gratuit, déjà payé via abonnement)
2. Sinon → consommé en crédits achetés
3. Si tu n'as ni quota ni crédits → 402 + bouton "Acheter des crédits"

Détails : [Plans, crédits et quotas](plans-credits.md).

## Erreurs courantes

| Message | Cause | Action |
|---|---|---|
| "Cet article serait trop similaire" | Anti-cannibalisation | Reformule ou utilise Titre forcé |
| "Quota mensuel atteint et aucun crédit" | Plan épuisé pour ce mois | Acheter des crédits ou attendre le 1er du mois |
| "Erreur génération: timeout" | Claude API > 60s ou Serper down | Réessaie. Si récurrent, signale via support |
| "Langue non autorisée pour ce site" | `available_languages` du Site exclut la langue choisie | Site Settings → Available languages → coche la langue |
| "WP unreachable: ..." (mode WordPress) | Site WP down ou REST API désactivée | Voir [troubleshooting WordPress](connect/wordpress.md#dépannage) |
