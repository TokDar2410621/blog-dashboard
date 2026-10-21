# Plans, crédits et quotas

Quatre plans mensuels, plus des crédits à la pièce quand ton quota d'articles est épuisé.

## Plans

| | Essai | Solo | Pro | Agence |
|---|---|---|---|---|
| Prix CAD/mois | **0$** | **29.99$** | **89.99$** | **199.99$** |
| Sites | 1 | 1 | 2 | 5 |
| Articles générés / mois | 1 | 8 | 60 | 200 |
| Mots-clés suivis | 0 | 10 | 30 | 100 |
| Accès par jeton (API REST, connecteur MCP, n8n) | ❌ | ❌ | 30 req/h | 200 req/h |

Sites, articles, mots-clés et accès par jeton : ce sont les limites que l'application applique selon ton plan. Le plan Essai ne demande pas de carte.

Les prix affichés sont en CAD. Le paiement passe par Stripe Checkout et accepte les codes promo.

### Plus de 5 sites ou besoin sur mesure

Aucun plan au-delà d'Agence n'est en libre-service. Écris à `tokamdarius@gmail.com` avec le sujet "Plan Enterprise - demande sur mesure" (bouton **Nous contacter** sur `/billing`).

## Crédits à la pièce

1 crédit = 1 article généré. Les crédits servent seulement quand ton quota mensuel est épuisé. Ils **n'expirent jamais** : ton solde passe d'un mois à l'autre.

| Pack | Crédits | Prix |
|---|---|---|
| Petit boost | 10 | 25$ |
| Boost moyen | 50 | 99$ |
| Gros volume | 200 | 299$ |

Achat : `/billing` → carte **Crédits achetés** → bouton **Acheter** sous le pack → Stripe Checkout. Les crédits arrivent sur ton solde quand Stripe confirme le paiement. Un même paiement ne peut pas être crédité deux fois.

Quand une génération est bloquée faute de quota, le générateur propose aussi les boutons **+10 crédits · 25$** et **+50 crédits · 99$**.

La carte **Crédits achetés** affiche ton solde et l'historique de tes 30 dernières transactions.

## Ce qui consomme ton quota

Seules ces actions décomptent un article (ou un crédit) :

- **Générer un article** : générateur du tableau de bord, `POST /api/v1/sites/<id>/generate/`, outil MCP `gridar_generate_article`.
- **Générer un article frère traduit** : `POST /api/v1/sites/<id>/articles/<slug>/generate-sister-article/`, outil MCP `gridar_generate_sister_article`.
- **Générer une landing par IA** : `POST /api/v1/sites/<id>/landings/generate/`, outil MCP `gridar_generate_landing`.

Un aperçu (mode dry run du générateur) ne consomme rien. Un article ou une landing créés à la main non plus.

Par jeton, chaque appel compte aussi dans ta limite horaire. Voir [API REST publique](api.md).

## Mécanique de quota détaillée

### Quota mensuel d'articles

- **Reset** : le compteur suit le mois civil en UTC (clé `AAAA-MM`). Un nouveau mois repart à zéro. Pas de pro-rata.
- **Décompte** : après une génération réussie. Une génération qui échoue ne consomme rien.
- **Où le voir** :
  - `/billing` : barre "Articles ce mois-ci", rouge à partir de 90 %.
  - Barre latérale du tableau de bord : indicateur compact, ambre à partir de 80 %, rouge quand le quota et les crédits sont épuisés.
  - Générateur d'articles : bannière à partir de 70 %.
- **Bannière du générateur** :
  - 70 à 99 % : "Plus que X articles ce mois-ci".
  - 100 % avec des crédits : "Tu utilises maintenant tes crédits".
  - 100 % sans crédit : génération bloquée, boutons pour acheter des crédits ou voir les plans.

### Logique de consommation

Pour chaque génération :

1. **Quota mensuel non épuisé** → le compteur du mois augmente de 1.
2. **Quota épuisé + crédits ≥ 1** → ton solde baisse de 1 crédit.
3. **Quota et crédits épuisés** → la génération est refusée : HTTP 402 avec `"quota_exceeded": true`.

Ton quota inclus passe toujours avant tes crédits achetés.

### Limites de sites

Vérifiée quand tu **crées un nouveau site** : blog hébergé, connexion WordPress, Shopify ou Webflow.

| Plan | Limite |
|---|---|
| Essai / Solo | 1 |
| Pro | 2 |
| Agence | 5 |

- Seuls tes sites actifs comptent.
- **Reconnecter** un site WordPress, Shopify ou Webflow déjà connecté ne prend pas de place : Gridar retrouve le site existant.
- Limite atteinte → HTTP 402 avec `"limit_type": "sites"`.

### Limites de mots-clés suivis

Comptées **sur l'ensemble de tes sites actifs**, pas par site. Un compte Pro avec 30 mots-clés peut les répartir 15 + 15 sur 2 sites, ou 30 + 0.

| Plan | Limite |
|---|---|
| Essai | 0 |
| Solo | 10 |
| Pro | 30 |
| Agence | 100 |

- **Réactiver** un mot-clé retiré compte comme un ajout : il te faut une place libre.
- Limite atteinte → HTTP 402 avec `"limit_type": "keywords"`.

## Stripe - facturation

- **Souscription** : `/billing` → bouton **Souscrire** (ou **Passer à** suivi du nom du plan) → Stripe Checkout.
- **Gérer mon abonnement** : ce bouton, visible avec un plan payant actif, ouvre le portail client Stripe. C'est là que tu modifies ta carte, consultes tes factures et annules.
- **Données de carte** : Stripe les traite. Gridar garde seulement les identifiants Stripe de ton client et de ton abonnement.

## Changer de plan ou annuler

- **Changement de plan** : Gridar lit ton plan dans les événements que Stripe lui envoie. Le nouveau plan et ses limites s'appliquent dès que Stripe confirme le changement.
- **Annulation en fin de période** : `/billing` affiche "Annulation effective le" suivi de la date de fin.
- **Fin de l'abonnement** : ton compte repasse au plan Essai. Rien n'est supprimé : tes sites restent actifs, tes mots-clés restent dans ta liste, tes articles publiés restent en ligne. Les limites de l'Essai s'appliquent : pas de nouveau site tant que tu en as un actif, aucun nouveau mot-clé, 1 article généré par mois.
- **Paiement refusé au renouvellement** : ton abonnement passe en statut `past_due`. Ton plan et ses limites restent en place jusqu'à ce que Stripe annule l'abonnement.

Voir aussi : [API REST publique](api.md), [Intégrations](integrations.md), [FAQ](faq.md).
