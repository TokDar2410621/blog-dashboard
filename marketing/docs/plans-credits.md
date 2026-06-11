# Plans, crédits et quotas

Pricing transparent : 5 paliers + crédits à la pièce pour les pics ponctuels.

## Plans

| | Essai | Solo | Pro | Agence | Enterprise |
|---|---|---|---|---|---|
| Prix CAD/mois | **0$** | **29.99$** | **89.99$** ⭐ | **199.99$** | sur mesure |
| Sites | 1 | 1 | 2 | 5 | 5+ |
| Articles / mois | 1 | 8 | 60 | 200 | sur mesure |
| Mots-clés tracking | 0 | 10 + GSC | 30 + GSC + alertes | 100 + alertes | sur mesure |
| Audit IA | basique | + brief de contenu | bulk + topic clusters | bulk + topic clusters | + |
| Lexique FR-CA | ❌ | ✓ | ✓ | ✓ | ✓ |
| Rapport PDF | ❌ | mensuel | hebdomadaire | hebdomadaire | hebdomadaire |
| API REST | ❌ | ❌ | 30 req/h | 200 req/h | sur mesure |
| Multi-domaines | ❌ | ❌ | ❌ | ✓ | ✓ |
| White-label | ❌ | ❌ | ❌ | ✓ | ✓ |
| Support | community | email <72h | email <48h | <8h | SLA + dédié |

⭐ = le plus populaire.

Tarifs en CAD, taxes québécoises (TPS+TVQ) ajoutées au checkout. Annulation en un clic, pas de lock-in.

## Crédits à la pièce

Quand ton quota mensuel est épuisé, tu peux acheter des crédits one-time pour continuer à générer ce mois-là. Les crédits **n'expirent jamais** et sont reportés d'un mois à l'autre.

| Pack | Crédits | Prix | $/article |
|---|---|---|---|
| Petit boost | 10 | 25$ | 2.50$ |
| Boost moyen ⭐ | 50 | 99$ | 1.98$ |
| Gros volume | 200 | 299$ | 1.50$ |

Les crédits sont consommés **uniquement après** que le quota mensuel soit épuisé. Tu ne perds donc jamais des crédits achetés en sur-utilisant ton plan - le quota gratuit est toujours dépensé en premier.

Achat : `/billing` → card "Crédits achetés" → choisis un pack → Stripe Checkout → crédits ajoutés à ton solde après paiement.

## Mécanique de quota détaillée

### Quota mensuel d'articles

- **Reset** : 1er de chaque mois UTC (pas de pro-rata)
- **Mesuré au moment de la génération réussie** (un dry_run ne consomme rien)
- **Visible sur** : `/billing` (barre de progression) + sidebar dashboard (indicateur compact)
- **Indicateur** :
  - Vert : usage < 70 %
  - Orange : 70-99 % (banner "Plus que X articles ce mois")
  - Rouge : 100 % atteint, pas de crédits → bouton désactivé + inline upgrade card
  - Ambre : 100 % atteint mais crédits dispo → notice "Tu utilises maintenant tes crédits"

### Logique de consommation

Pour chaque génération réussie :

1. **Quota mensuel non épuisé** → on incrémente le compteur mensuel (gratuit pour toi, déjà payé via abonnement)
2. **Quota mensuel épuisé + crédits ≥ 1** → on décrémente 1 crédit
3. **Quota et crédits épuisés** → HTTP 402 + bouton "Acheter des crédits" + "Voir les plans"

Cette logique garantit que tu ne **gaspilles jamais** un crédit acheté tant que ton plan a encore du quota disponible.

### Limites de sites

Vérifié au moment de **créer un nouveau site** (connecter un WP/Shopify/Webflow ou créer un blog hébergé).

| Plan | Limite |
|---|---|
| Essai / Solo | 1 |
| Pro | 2 |
| Agence | 5 |
| Enterprise | sur mesure |

Si tu downgrades vers un plan avec moins de sites, tes sites existants restent (rien n'est supprimé). Tu ne pourras simplement pas en créer de nouveaux tant que tu n'es pas en-dessous de la limite.

**Reconnect** d'un site existant ne consomme PAS un slot supplémentaire (on détecte que le site existe déjà).

### Limites de mots-clés trackés

Comptées **across tous tes sites**, pas par site. Donc un user Pro avec 30 mots-clés peut les répartir 15+15 sur 2 sites, ou 30+0.

| Plan | Limite |
|---|---|
| Essai | 0 |
| Solo | 10 |
| Pro | 30 |
| Agence | 100 |
| Enterprise | sur mesure |

Si tu downgrades, tes mots-clés existants restent actifs mais tu ne pourras plus en ajouter tant que tu n'es pas sous la limite.

**Réactiver** un mot-clé désactivé ne consomme pas un slot (déjà compté dans ton total).

## Stripe - facturation

- **Méthodes acceptées** : carte (Visa, MC, Amex, Discover), Apple Pay, Google Pay
- **Devise** : CAD (Stripe convertit automatiquement si ta carte est USD/EUR)
- **Taxes** : TPS 5 % + TVQ 9.975 % auto-calculées et facturées si Québec
- **Factures** : générées automatiquement, accessibles via le portail Stripe (`/billing` → "Gérer mon abonnement")
- **Annulation** : un clic dans le portail Stripe. Pas de pro-rata - ton accès continue jusqu'à la fin de la période payée
- **Sécurité** : on ne touche jamais à tes infos de carte (PCI-DSS via Stripe)

## Upgrade / Downgrade en cours d'abonnement

**Upgrade** (Solo → Pro par ex.) : effet immédiat. Stripe pro-rata l'écart. Tu accèdes aux features Pro tout de suite.

**Downgrade** (Pro → Solo) : effet à la fin de ta période en cours. Tes sites/mots-clés au-dessus de la nouvelle limite ne sont pas supprimés (mais figés en lecture).

**Cancel** : effet à la fin de la période. Plan = `free` à expiration. Tes sites passent en `is_active=False`. Tes articles publiés sur leur CMS natif (WP/Shopify/Webflow) restent en place.

## Plan Enterprise

Pour les besoins qui sortent du cadre :
- 5+ sites
- Volume custom (1000+ articles/mois, 500+ mots-clés)
- White-label complet (ta marque, ton domaine pour le dashboard)
- Intégrations privées (CRM custom, n8n self-hosted, ERP)
- SLA contractuel (uptime, response time)
- Comptable dédié + onboarding personnalisé

Contact : `tokamdarius@gmail.com` avec sujet "Plan Enterprise - demande sur mesure".
