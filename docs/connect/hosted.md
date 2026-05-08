# Mode hébergé (Blog clé-en-main)

Pour les sites custom (React, Vue, Astro, Next.js, ou n'importe quoi d'autre) qui n'ont pas de CMS, ou pour les utilisateurs qui ne veulent rien toucher chez leur dev. **Une seule manipulation** : un CNAME chez ton registrar.

## Comment ça marche

1. Tu nous fournis un sous-domaine où tu veux que ton blog vive (ex : `blog.tonsite.ca`)
2. Tu ajoutes un CNAME chez ton registrar pointant vers `cname.vercel-dns.com`
3. Vercel + nous configurons le sous-domaine sur notre infra Next.js
4. Tu génères des articles depuis Blog Dashboard → ils sont publiés à `blog.tonsite.ca/article-slug`

Les articles vivent dans **notre** Postgres mais sont servis sur **ton domaine** (sous-domaine). Le branding (logo, couleur, fonts) est appliqué automatiquement à partir du scan qu'on a fait au connect.

## Étapes

### 1. Crée le site dans Blog Dashboard

Sites → **Blog clé-en-main**. Tu remplis :

- **Nom du site** : libellé interne (ex : "Mon blog SaaS")
- **Domaine** : ton domaine principal (ex : `tonsite.ca`)
- **Database URL** : laisse vide - on utilise notre Postgres hébergé (le mode "hébergé" pur)

Crée. Tu arrives au dashboard.

### 2. Configure le sous-domaine

Site Settings → onglet **Domaine du blog public**.

Champ "Public blog domain" : entre le sous-domaine que tu veux (ex : `blog.tonsite.ca`).

Sauvegarde. On affiche les instructions DNS exactes :

```
Type     CNAME
Hôte     blog
Cible    cname.vercel-dns.com
TTL      3600
```

Va chez ton registrar (GoDaddy, OVH, Namecheap, Cloudflare DNS, ...) → DNS settings → ajoute l'enregistrement.

### 3. Vérification

Une fois la propagation DNS faite (souvent 5-30 min, parfois 24h max) :
- `dig blog.tonsite.ca` (Mac/Linux) ou `nslookup blog.tonsite.ca` (Windows) doit retourner Vercel
- Va sur `https://blog.tonsite.ca` → tu vois ta page d'accueil de blog vide avec ton branding

Si tu vois "404" ou "Domain not configured", attends quelques minutes et re-teste.

### 4. Génère ton premier article

Dashboard → **Générer un article** → suis le workflow standard.

L'article sera disponible immédiatement à `https://blog.tonsite.ca/article-slug`.

## Avantages du mode hébergé

- **Zéro code chez toi** : pas de fichiers à coller, pas de redéploiement
- **Build instantané** : on régénère les pages à chaque article (Next.js ISR)
- **SEO optimisé out-of-the-box** : sitemap.xml + RSS auto-générés à `blog.tonsite.ca/sitemap.xml`
- **Performance** : Vercel Edge CDN, cover images optimisées WebP, lazy load
- **Mobile-friendly + dark mode**

## Limites SEO du mode sous-domaine

Google traite les sous-domaines comme des sites séparés. Concrètement :
- ✅ Le sous-domaine **est indexé** et reçoit du trafic search
- ✅ Tes articles peuvent ranker top 1 sur leurs mots-clés
- ✅ Tu **bonifies indirectement** ton domaine principal via les liens internes (blog → home → produit)
- ⚠️ Tu ne bonifies pas DIRECTEMENT le domaine racine sur les mots-clés des articles

Pour un SEO 100 % sur le domaine racine, le mode [externe](external.md) (subfolder via API REST) ou WordPress sur ton domaine sont des meilleures options.

## Dépannage

| Erreur | Cause | Fix |
|---|---|---|
| `https://blog.tonsite.ca` retourne 404 | Sous-domaine pas encore propagé | Attends 30 min, re-teste avec `dig` |
| Le branding (logo/couleur) n'est pas là | Auto-scan n'a rien trouvé sur ton domaine | Site Settings → onglet Branding → "Scanner" pour relancer, ou édite manuellement |
| `Domain configuration error` Vercel | CNAME mal pointé | Vérifie : type CNAME, nom = juste le sous-domaine (`blog`, pas `blog.tonsite.ca`), valeur = `cname.vercel-dns.com` |
| Articles pas indexés par Google | Sitemap pas soumis | Soumets `https://blog.tonsite.ca/sitemap.xml` dans Google Search Console |
