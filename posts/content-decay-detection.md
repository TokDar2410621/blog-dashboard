---
title: Content decay — pourquoi tes meilleurs articles perdent du trafic (et comment le récupérer)
slug: content-decay-detection
date: 2026-04-10
author: Darius Tokam
excerpt: Tes 3 articles qui drivaient 60 % de ton trafic en 2023 sont passés sous la barre des 50 visites/mois. C'est le content decay. Voici comment l'identifier en 5 min et le réparer en 30.
tags: [content-decay, seo, refresh]
---

Si ton blog a plus de 18 mois, statistiquement, 30-50 % de ton trafic SEO vient de **2-5 articles seulement**. Ce sont tes "money pages". Et statistiquement aussi, **ces articles perdent du trafic en ce moment**, sans que tu le saches.

C'est ce qu'on appelle le **content decay**. Voici comment le diagnostiquer et le réparer.

## Définition concrète

Un article est en content decay quand :

- Il a plus de 6 mois d'existence
- Il a déjà été dans le top 10 Google sur au moins une requête
- Il a perdu > 30 % de son trafic organique sur les 90 derniers jours, mesuré via Google Search Console

C'est différent d'un article qui n'a JAMAIS performé (ça, c'est un problème de stratégie, pas de decay).

## Pourquoi ça arrive

5 causes classiques, par ordre de fréquence :

1. **Concurrents publient mieux et plus récent.** Google récompense la fraîcheur. Si ton article date de 2023 et que ton concurrent vient de publier un truc plus complet en 2026, tu chutes.
2. **Information périmée.** Tu disais "le programme XYZ donne 5000 $", le programme a changé à 7000 $, Google détecte l'incohérence avec les sources récentes et te déclasse.
3. **Search intent qui dérive.** Le mot-clé "meilleur CRM" voulait dire "comparatif d'outils" en 2023, il veut dire "comparatif avec démo vidéo" en 2026. Si tu n'as pas adapté, tu sors.
4. **Backlinks qui s'évaporent.** Les sites qui te linkaient ferment ou repensent leurs articles sans toi.
5. **Core update Google.** Septembre 2023, mars 2024, août 2025 — chaque update redistribue 10-30 % du trafic.

## Comment le détecter (3 méthodes)

### Méthode 1 : Google Search Console manuelle (gratuit, 30 min/mois)

1. GSC → Performance → comparer "Last 28 days" vs "Previous period"
2. Trier par perte absolue de clics
3. Identifier les 5 articles qui ont le plus chuté

Bon pour un blog avec moins de 50 articles. Devient ingérable au-delà.

### Méthode 2 : Outils SEO automatisés (~30-100 $/mois)

Ahrefs, SEMrush ont des features "lost positions". Te flagge automatiquement les chutes.

### Méthode 3 : Gridar Content Decay (inclus dans tous les plans)

Le module Content Decay de Gridar tourne en arrière-plan : il croise tes données GSC connectées avec les positions tracker quotidiennes et te flagge automatiquement les chutes > 30 %.

Tu reçois un email hebdomadaire : "3 articles en decay cette semaine, voici lesquels et pourquoi."

## Comment réparer (le playbook en 5 étapes)

### Étape 1 : Identifier la cause

Pour chaque article flaggé, ouvre-le en mode incognito et compare-le aux 3 premiers résultats actuels sur sa requête principale. Cherche :

- Ton article a-t-il moins de mots que les concurrents ? (souvent oui)
- Ton article cite-t-il des sources de 2023 alors que les concurrents ont des sources 2026 ?
- Les concurrents ont-ils des images/vidéos/tableaux que tu n'as pas ?
- L'intent semble-t-il avoir changé (le top 10 actuel est-il très différent de ce que tu cibles) ?

### Étape 2 : Mettre à jour les infos périmées

Stats, dates, prix, programmes, lois — tout doit refléter 2026.

### Étape 3 : Augmenter la profondeur

Si ton article fait 800 mots et que les top 3 font 2200 mots, ajoute 1500 mots. Sections supplémentaires, FAQ, tableaux comparatifs.

### Étape 4 : Rafraîchir les signaux

- Update la `<meta property="article:modified_time">`
- Ajoute "Mis à jour le [date]" en haut de l'article
- Ajoute 2-3 backlinks internes vers tes articles plus récents
- Republie (sans changer l'URL) — Google va re-crawler dans 1-7 jours

### Étape 5 : Re-promouvoir

LinkedIn, Twitter, ton mailing list. Refresher un article + en parler 30 minutes = effet souvent supérieur à publier un nouvel article.

## Le shortcut Gridar

Pour chaque article flaggé en decay, Gridar te propose un bouton "Régénérer" qui :

1. Recharge le brief de contenu avec les nouvelles données 2026
2. Compare ton article au top 3 actuel
3. Génère une version refresh qui garde ton angle mais comble les écarts
4. Te montre un diff avant/après
5. Tu publies en un clic — l'URL reste, Google ne perd pas tes signaux historiques

Temps total : 5 minutes par article.

## Stats internes (200 articles dogfooding)

Sur 200 articles qu'on a passés au playbook refresh :

- **63 %** ont retrouvé leur niveau de trafic d'avant le decay dans les 30 jours
- **23 %** ont dépassé leur pic historique (refresh = excellence > original)
- **14 %** sont restés à leur niveau dégradé (cause = autre, type changement de SERP intent)

Plus important : le **temps moyen pour rentabiliser le refresh** (recover assez de clics organiques pour payer le coût de re-rédaction) est de **18 jours**.

## Lectures liées

- [SEO automatique pour PME](/blog/seo-automatique-pme-quebecoise)
- [E-E-A-T pour PME québécoises](/blog/eeat-quebec-pme)
