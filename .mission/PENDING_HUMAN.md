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

## Issu du sprint conversion 2026-05-19 (A + C + B livres)

### A - Trust signals + blur + count en temps reel sur /audit (commit 908ef13)
- [ ] **Tester** apres redeploiement Vercel : visiter `gridar.app/audit`, verifier que la ligne sociale affiche bien "{N} audits ce mois-ci · Resultat <30s · Loi 25 + RGPD" et que les 7 recos plus bas sont **floutees** tant qu'on n'a pas entre d'email. Apres email gate -> le flou doit disparaitre.

### C - PDF telechargeable du rapport (commit bc8995c)
- [ ] **Migrate** sur Railway (rien a faire pour cette phase, mais le package `xhtml2pdf` doit etre dans le rebuild du Dockerfile Railway, ce que `pip install -r requirements.txt` couvre).
- [ ] **Tester** : lancer un audit sur `gridar.app/audit`, cliquer "Telecharger en PDF", verifier que le PDF telecharge et qu'il est lisible (police + couleurs + CTA en bas).
- [ ] **Si tu fais ton outreach LinkedIn** : copie-colle l'audit du domaine cible dans le browser (sans le runner) → ouvre `gridar.app/api/public/audit/{domain}/pdf/` directement → attache le PDF au DM.

### B - Sequence d'emails apres capture lead (commit 966d12c)
- [ ] **Compte Resend** : creer un compte sur https://resend.com (free tier 3000 emails/mois).
- [ ] **Verifier le domaine d'envoi** : ajouter `gridar.app` (ou un sous-domaine `mail.gridar.app`) dans Resend, copier les 3 records DNS (SPF, DKIM, DMARC) chez ton registrar.
- [ ] **Generer un API key** dans Resend dashboard.
- [ ] **Ajouter sur Railway** les env vars :
  - `RESEND_API_KEY=<la cle>`
  - `RESEND_FROM=Gridar <darius@gridar.app>` (utilise un From de ton domaine verifie)
- [ ] **Migrate 0028 LeadEmailSent** : `railway ssh` + `python manage.py migrate`.
- [ ] **Configurer le cron quotidien** sur Railway : Settings -> Cron Jobs -> Add Cron -> command: `python manage.py send_lead_sequence`, schedule: `0 13 * * *` (13h UTC = 9h America/Toronto).
- [ ] **Tester en local** : `python manage.py send_lead_sequence --dry-run` pour voir combien de leads sont dus a chaque step sans envoyer.
- [ ] **Tester avec UN lead reel** : `python manage.py send_lead_sequence --lead-id=<ton id>` pour valider la chaine complete avant le cron auto.
- [ ] **Optionnel - construire la page /unsubscribe** : un simple flip `Lead.consented_marketing = False` quand on visit `gridar.app/unsubscribe?email=X`. Le lien est deja dans tous les emails mais l'endpoint n'existe pas encore - sans ca tu enfreins techniquement la Loi 25.

## Avant juin 24, 2026 (deadline imposee par Google)

- [ ] Migrer la generation d'images cover de `imagen-4.0-fast-generate-001` (deprecated 24 juin) vers `gemini-2.5-flash-image` (Nano Banana). Cherche le TODO inline dans `backend/sites_mgmt/views.py` -> classe `GenerateImageView`.

## Conventions

Quand Darius fait une de ces actions :
1. Coche `[x]`
2. Garde la ligne (audit trail). On archivera dans un autre fichier quand >100 lignes.
3. Si une action revele un autre blocker, l'ajouter ici en sous-puce.
