---
title: E-E-A-T pour PME québécoises — 6 signaux que Google attend de toi
slug: eeat-quebec-pme
date: 2026-04-24
author: Darius Tokam
excerpt: Le Helpful Content Update a fait disparaître 40 % des blogs anonymes. Voici les 6 signaux E-E-A-T spécifiques au contexte québécois — et comment les générer en 30 minutes.
tags: [eeat, seo, quebec]
---

Le Helpful Content Update (HCU) de septembre 2023, puis le Core Update de mars 2024, ont massivement dégradé deux types de contenu : (1) les blogs anonymes ou pseudonymes sans signal d'identité, (2) le contenu généré IA sans relecture humaine identifiable.

Pour une PME québécoise, c'est en réalité une **opportunité** : la barrière à passer est basse, mais peu de tes concurrents l'ont fait.

## Qu'est-ce que E-E-A-T

C'est l'acronyme officiel de Google (depuis fin 2022) pour 4 signaux qu'ils utilisent pour évaluer la qualité d'une page :

- **E**xperience : as-tu vécu ce dont tu parles ?
- **E**xpertise : es-tu qualifié sur le sujet ?
- **A**uthoritativeness : ton site fait-il référence dans le domaine ?
- **T**rustworthiness : peut-on te faire confiance ?

Le double E (Experience + Expertise) a été ajouté en décembre 2022 spécifiquement pour récompenser le contenu first-person ("j'ai testé, voici ce qui s'est passé") vs le contenu théorique copié-collé.

## Les 6 signaux concrets que Google checke

### 1. Auteur identifié avec nom complet + photo + bio

`<script type="application/ld+json">` Person schema, avec :

```json
{
  "@type": "Person",
  "name": "Darius Tokam",
  "image": "https://tonsite.ca/team/darius.jpg",
  "jobTitle": "Fondateur, Arivex Studio",
  "sameAs": [
    "https://www.linkedin.com/in/dariustokam",
    "https://github.com/TokDar2410621"
  ]
}
```

Sans `sameAs`, Google ne peut pas désambiguïser ton identité. **2 profils sociaux minimum.**

### 2. Adresse physique vérifiable au Québec

Schema `LocalBusiness` avec `addressRegion: "QC"` + numéro de téléphone québécois (`+1-450-xxx-xxxx`). Pour une PME locale, c'est le signal le plus puissant.

### 3. Numéro d'entreprise du Québec (NEQ)

Mentionne ton NEQ dans le footer ou sur la page "À propos". Pas de schema obligatoire, mais ça rassure Google ET tes utilisateurs ("vraie entreprise enregistrée"). 5 secondes à ajouter.

### 4. Cas client ou témoignages avec noms réels

Pas "Jean D., satisfait" — "Jean Doucet, propriétaire de Café Bélanger à Sherbrooke". Les noms abstraits sont devenus suspects post-HCU.

### 5. Date de dernière mise à jour visible

`<meta property="article:modified_time" content="2026-05-09T...">`. Plus visible : "Mis à jour le 9 mai 2026" en haut de l'article. Google récompense la fraîcheur récente.

### 6. Auteur invité = lien vers son profil externe

Si tu fais publier un dentiste sur ton blog "santé bucco-dentaire", lie son nom à sa fiche LinkedIn + sa fiche de l'Ordre des dentistes du Québec. **Authority par association.**

## L'erreur classique des blogs IA en 2025

90 % des blogs qui ont disparu post-HCU avaient :
- Aucun auteur identifié (juste "Admin" ou "L'équipe")
- Aucun schema `Person` ou `Organization`
- Aucun signal géolocalisé
- Contenu identique mot pour mot à 200 autres blogs

Google a appris à détecter ce pattern.

## Le score Gridar EEAT

Gridar audite automatiquement tes articles sur les 6 signaux ci-dessus et te donne un score 0-100. Pour atteindre 100 :

1. Remplir l'onglet **EEAT** dans **Site Settings** (Bio, photo, LinkedIn)
2. Activer le schema `Person` (généré automatiquement)
3. Connecter ton NEQ dans l'onglet **Branding** (apparaît dans le schema `LocalBusiness`)
4. Lier au moins 2 profils sociaux

5 minutes pour passer de 30/100 à 95/100. Les sites avec un EEAT score >80 ranquent en moyenne 30 % plus haut sur les mêmes mots-clés (étude interne sur 200 articles dogfooding).

## Lectures liées

- [Comment ranker sur Google au Québec](/blog/comment-ranker-google-quebec-2026)
- [Le piège du SEO français](/blog/seo-bilingue-fr-ca-piege)
