# Architecture actuelle (snapshot 2026-05-04)

À mettre à jour quand on ajoute/refactore une feature SEO majeure. Doit rester < 200 lignes — c'est un **résumé** pour briefer un nouvel agent, pas la doc complète.

## Stack

- **Backend** : Django 5.x + DRF, hosted sur Railway. JWT cookie + Bearer (HS256).
- **Frontend** : React + Vite + TypeScript, shadcn/ui, Tailwind, react-i18next FR/EN, react-query, react-router. Hosted sur Vercel.
- **Multi-tenant** : `Site.database_url` détermine le mode :
  - `is_hosted` (database_url null) → `HostedPost` dans la DB du dashboard.
  - external → `BlogPost.objects.using(alias)` sur la DB du client.
- **APIs externes** : Anthropic Claude (génération), Gemini 2.5 flash (audit/fix/translation), Serper (SERP/competitors/backlinks/PAA), Google PageSpeed, Google Search Console, Pexels.

## Fichiers critiques

| Fichier | Rôle |
|---|---|
| `backend/sites_mgmt/views.py` | ~3000 lignes, hub des vues API. Pattern : APIView + UserRateThrottle. |
| `backend/sites_mgmt/models.py` | `Site` (avec `database_url`, `api_key`, `default_language`, `available_languages`, `gsc_*`), `HostedPost`, `HostedCategory`, `HostedTag`. |
| `backend/sites_mgmt/article_generator.py` | ~1200 lignes, pipeline génération article via Claude REST direct. Inclut anti-cannibalization Jaccard. |
| `backend/sites_mgmt/blog_adapter.py` | Vues SQL pour adapter des DB externes au schéma `BlogPost` canonique. |
| `backend/sites_mgmt/serializers.py` | DRF serializers. |
| `backend/sites_mgmt/urls.py` | 36+ routes. |
| `backend/blog/models.py` | `BlogPost` canonique (utilisé via `using(alias)`). |
| `src/components/SEOAnalyzer.tsx` | ~2600 lignes, contient toutes les sections SEO (audit, fix, keywords, competitors, schema, alt-text, cannibalization, GSC, link suggestions). |
| `src/pages/dashboard/PostEditor.tsx` | Éditeur d'article + bouton Traduire (mirror status source). |
| `src/pages/dashboard/AIGenerator.tsx` | Wizard de génération IA. |
| `src/lib/api-client.ts` | `authFetch` (JWT). |

## Endpoints existants (résumé)

### Génération
- `POST /generate-tags/`, `POST /sites/<id>/generate/`, `POST /sites/<id>/generate-inline/`
- `POST /generate-image/`, `POST /upload-image/`, `GET /images/<uid>/`

### SEO core
- `POST /seo-audit/`, `POST /seo-fix/`, `POST /seo-suggest/`, `POST /seo-synonyms/`, `POST /seo-cache/clear/`, `POST /seo-schema/`
- `POST /competitors/`, `POST /keyword-research/`, `POST /page-speed/`, `POST /backlinks/`
- `GET /sites/<id>/cannibalization/`, `GET /sites/<id>/link-suggestions/`

### Autres
- `POST /pexels/search/`, `POST /serper/images/`
- `POST /translate/` (sans save)
- GSC : `/sites/<id>/gsc/oauth-url/`, `/oauth-callback/`, `/queries/`

### Public API (consommée par Arivex, LocaSur, TokamDarius)
- `GET /public/sites/<id>/`, `GET /public/sites/<id>/posts/` (avec dedup translation_group)
- `GET /public/sites/<id>/posts/<slug>/`, `/translations/`, `/categories/`

## Patterns à respecter pour ajouter une feature

**Backend (vue SEO)** :
```python
class XxxView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]
    throttle_scope = 'ai_generate'

    def post(self, request):
        # 1. validation
        # 2. cache check : key = _seo_cache_key('xxx', *parts); cached = cache.get(key); if cached: return Response(cached)
        # 3. call Gemini / Serper / Anthropic
        # 4. cache.set(key, result, 3600)
        # 5. return Response(result)
```

**Frontend (composant SEO)** :
- shadcn/ui : `Card`, `CardContent`, `CardHeader`, `Button`, `Input`, `Select`, `Tabs`, `Skeleton`, `Tooltip`
- `lucide-react` icons
- `@/lib/api-client` → `authFetch`
- `@tanstack/react-query` → `useQuery` / `useMutation`
- `react-i18next` → tous les libellés via `t("clé")`, ajouter clés FR + EN dans `src/i18n/`
- toast via `sonner`

## DB / migrations

- `sites_mgmt/migrations/` — historique. Avant d'ajouter un modèle, créer `python manage.py makemigrations sites_mgmt`.
- Ne pas casser la compat Arivex (contrainte `unique(slug, language)` côté external).

## Tests

- Pas de framework formel en place.
- Validation manuelle : `python backend/manage.py check` + `npm run build` + curl.
