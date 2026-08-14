# Tier 6 : brancher les modules portes

Les modules sont ecrits, testes et commites. Ils sont tous en Python pur, sans
ORM et sans reseau : ils prennent des donnees, ils rendent des donnees. Reste a
les brancher. Ce fichier dit ou, pour chacun.

Rapports complets des agents (API detaillee, adaptations, pieges) :
`C:\Users\Darius\AppData\Local\Temp\claude\c--Users-Darius-Desktop-blog-dashboard\f14a803d-4819-46a8-a9af-bc2316c43d40\tasks\weg3xcn6t.output`

Regle commune : aucun module ne fait de reseau. L'appelant fetch avec
`from .url_safety import safe_get` puis passe le HTML. C'est volontaire, ca
garde les modules testables hors ligne et ca force le passage par la protection
SSRF.

## Rang 2 : drift_rules (surveillance de derive)

`capture_snapshot(html, url)` puis `compare_snapshots(before, after)` et
`summarize_findings(findings)`. 17 regles, findings deja rediges en francais.

Piege : apres `capture_snapshot`, l'appelant DOIT poser
`snap['status_code'] = resp.status_code` avant de sauver, sinon la regle
`code_http_erreur` reste muette pour toujours.

A construire : un modele `PageSnapshot` (FK Site, url, captured_at, payload
JSONField non eclate en colonnes) et si tu veux l'historique un `DriftCheck`
(FK Site, url, checked_at, findings JSONField, compteurs par severite).
Endpoints : `POST /sites/<id>/drift/baseline` et `POST /sites/<id>/drift/check`.
Ecran : liste avec pastille de severite, colonnes avant/apres. C'est ce module
qui transforme un audit ponctuel en abonnement, donc l'ecran compte.

## Rang 5 : schema_validator (bloquer le schema casse)

`validate_jsonld(data)` renvoie `[{level, path, message}]`, `path` est un
pointeur JSON affichable. `has_blocking_errors(issues)` est le predicat a
brancher sur le bouton Publier.

A brancher : avant de passer un post ou une landing en `published`, et sur la
sortie du generateur de schema de `views.py` (~L2806) qui livre aujourd'hui du
JSON-LD sans le valider. Rouge pour error, ambre pour warning.

## Rang 6 : content_verify (chiffres inventes)

`verify_text(text)` renvoie le rapport complet, `find_unsourced_claims(text)`
la liste seule.

A brancher en priorite sur `gridar_audit_article`. Aujourd'hui cet audit note
93/100 un article bourre de statistiques fabriquees et cite meme les faux
chiffres comme preuve d'E-E-A-T. C'est documente dans le backlog du cerveau
(bug 15). Ce module est le seul filet possible en aval du generateur.

## Rang 8 : schema_builder (produire du schema)

`build_profile_page(author)`, `build_service(site, service)`,
`validate_product(product)`.

Le ProfilePage avec `sameAs` sert directement la visibilite IA : il fait de la
marque une entite reconnaissable. A brancher sur les champs auteur de
SiteSettings. Faire passer toute sortie par `schema_validator` avant livraison.

## Rang 10 : gbp_lint (fiche Google Business perimee)

`lint_gbp_references(html, url)`. A brancher dans l'audit de site, sur le HTML
deja recupere. Defaut tres concret sur les PME locales, avec la date de retrait
citee, ce qui rend la recommandation credible aupres du client.

## Rang 13 : html_parse (remplacer le parsing par regex)

`extract_seo_signals(html, base_url)` renvoie 20 cles toujours presentes.

A substituer au bloc d'expressions regulieres de `_crawl_homepage`
(`views.py`). Attention : c'est le chemin de l'audit public, donc a tester avec
soin. Le module aplatit les conteneurs `@graph`, ce que le regex ne faisait pas.

## Rang 14 : sitemap_discovery

`discover_sitemaps(domain)` et `parse_sitemap(xml_text)`. Fetch deja cable sur
`safe_get`. A ajouter a l'audit de site : un sitemap absent ou cross-host est un
signal fort, et le cross-host est un indice de piratage.

## Rang 15 : google_updates (dater une chute)

`traffic_drop_report(drop_date, window_days, surface)` est la fonction a
appeler, pas `explain_traffic_drop` seule : elle distingue "aucune update
confirmee" de "la liste s'arrete avant ta date, impossible de conclure".

Afficher `freshness.message` en permanence sous la reponse, sinon un silence se
lit comme une absence d'update. Badge orange si `freshness.is_stale`.

ACTION HUMAINE RECURRENTE : le fichier `data/google_updates.json` porte
`last_verified: 2026-07-02`. Il passe en perime le 2026-08-31. Le re-verifier
contre status.search.google.com et bumper la date.

## Rang 17 : sxo (type de page contre SERP)

`classify_page_type(html, url)` puis `detect_mismatch(page_type, serp_types)`.

Repond a "ma page est parfaite et elle ne monte pas". Afficher les `signaux` a
cote du verdict : c'est ce qui evite le "votre page est mal typee, croyez-nous".
Les types du top 10 viennent de `serp_analyze`.

## Rang 20 : agent_ux (lisibilite par un agent IA)

`check_agent_readability(html, url)` renvoie un score 0-100 sur 6 criteres, avec
recommandations redigees.

Angle 2026 sur lequel presque aucun concurrent n'audite. Un critere sort du
denominateur quand il est sans objet, comme Lighthouse retire un audit N/A.

## Convergence a faire plus tard

Trois modules embarquent leur propre parseur HTML : `html_parse`, `sxo` et
`agent_ux`. Chacun est autonome par construction (les agents travaillaient en
parallele sans se voir). Une passe de consolidation pourrait n'en garder qu'un,
mais ce n'est pas un prerequis et ca peut attendre que les trois soient branches
et stables.
