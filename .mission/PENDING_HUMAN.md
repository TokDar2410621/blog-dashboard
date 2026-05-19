# Actions humaines en attente

Liste des trucs que JE (Claude) ne peux pas faire et qui bloquent la mission tant que Darius ne les fait pas.

Format : checkbox + courte description + lien si pertinent. Cocher `[x]` quand fait.

## Issu du pivot 2026-05-15 (4 phases livrees)

### Phase 1 - Audit site-level
- [ ] Aucune action humaine. Le code utilise des endpoints + env vars deja en place sur Railway. Visiter `/dashboard/<id>/audit-site` pour valider en prod apres redeploiement.

### Phase 2 - Blog subdomain plug-and-play (Vercel API)
- [ ] **Generer un Vercel API token** (https://vercel.com/account/tokens) avec scope au minimum `Project.Domain`. Scope par team si compte team.
- [ ] **Recuperer le Project ID** du projet public-blog (Vercel dashboard > public-blog > Settings > General > Project ID).
- [ ] **Ajouter sur Railway** les env vars :
  - `VERCEL_API_TOKEN=<token>`
  - `VERCEL_PROJECT_ID=<id>`
  - `VERCEL_TEAM_ID=<id>` (optionnel, si compte team)
- [ ] Tester en prod : Settings d'un site -> remplir `blog.example.com` -> Activer -> verifier que la card amber affiche les bonnes instructions CNAME.

### Phase 3 - Public audit page (lead magnet)
- [ ] **`python manage.py migrate`** sur Railway pour creer la table `sites_mgmt_lead` (migration 0027).
- [ ] **Tester** `gridar.app/audit` apres redeploiement Vercel. Verifier que l'audit termine en <30s et que l'email gate apparait.
- [ ] **Sales follow-up** : Django admin -> "Leads (audit gratuit)" -> filter par `consented_marketing=True` pour la liste de prospects opt-in.
- [ ] (Optionnel, plus tard) : configurer SMTP (Mailgun/SendGrid) pour envoyer le rapport detaille par email plutot que d'afficher la "deblocage" purement cote SPA.
- [ ] (Optionnel) Branchement du tracking : Plausible/Posthog event `public_audit_started` + `email_captured` pour mesurer la conversion.

### Phase 4 - WordPress plugin
- [ ] **Tester localement** : zip `wordpress-plugin/gridar-connector/` -> upload sur un WP de test -> activer -> Reglages > Gridar -> coller un token Gridar -> Connecter -> verifier que le Site apparait dans `gridar.app/sites`.
- [ ] **Soumettre a wordpress.org plugin directory** (validation 5-15 jours) :
  - Compte wordpress.org : https://wordpress.org/plugins/developers/add/
  - Upload du zip via la page de soumission
  - Reponses aux questions de l'equipe modero plugin (souvent : preuve que les permissions necessaires sont demandees, code review summary)
- [ ] **Listing dans le dashboard Gridar** : ajouter un bouton "Telecharger le plugin WordPress" sur la page de creation de site mode WP qui redirige vers le directory wordpress.org une fois publie.

## Heritees de sessions precedentes (toujours valides)

- [ ] Rotater les 6 secrets prod leakes en chat le 2026-05-12 : Stripe secret, webhook secret, Anthropic, Google OAuth secret, GitHub OAuth secret, Django SECRET_KEY.
- [ ] Creer un superuser Django : `railway ssh` + `python manage.py createsuperuser`.
- [ ] Mettre `STRIPE_PRICE_CREDITS_SMALL/MEDIUM/LARGE` sur Railway (sinon achat de credits crash).
- [ ] Mettre `VITE_API_URL=/api` sur Vercel (relatif, pour utiliser le proxy).
- [ ] Migration RAG : `railway ssh` puis `python manage.py migrate` + `python manage.py rebuild_site_memory --all` (apres avoir mis `VOYAGE_API_KEY` sur Railway si pas deja fait).
- [ ] Migration de la table Lead : `railway ssh` puis `python manage.py migrate`.
- [ ] Migration RAG feedback loop : meme commande (migration 0026 included dans le `migrate`).

## Avant juin 24, 2026 (deadline imposee par Google)

- [ ] Migrer la generation d'images cover de `imagen-4.0-fast-generate-001` (deprecated 24 juin) vers `gemini-2.5-flash-image` (Nano Banana). Cherche le TODO inline dans `backend/sites_mgmt/views.py` -> classe `GenerateImageView`.

## Conventions

Quand Darius fait une de ces actions :
1. Coche `[x]`
2. Garde la ligne (audit trail). On archivera dans un autre fichier quand >100 lignes.
3. Si une action revele un autre blocker, l'ajouter ici en sous-puce.
