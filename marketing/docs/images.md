# Gestion des images

3 sources d'images intégrées + upload manuel + alt-text auto par IA. Tout vit dans la **galerie d'images** du site.

## Galerie

**Sidebar → Images**

Liste toutes les images uploadées sur ce site (cover images, illustrations dans les articles, OG images). Pour chaque image :
- Aperçu thumbnail
- Nom de fichier
- Source (`pexels` / `serper` / `ai_gen` / `manual_upload`)
- Alt-text (modifiable inline)
- URL publique (à coller dans un article ou page)
- Articles qui l'utilisent
- Bouton supprimer

Filtres : par source, par usage (cover / inline / OG), par date.

## 4 sources d'images

### 1. Pexels (gratuit, recommandé par défaut)

API Pexels : photos haute qualité sous license CC0 (réutilisation libre, même commerciale).

- Recherche par mot-clé (FR ou EN)
- Filtres : portrait / paysage / carré, taille
- Prévisualisation avant insertion
- Stocké chez nous quand tu insères (pour stabilité - si Pexels delete, ton article continue de fonctionner)

Activé par défaut sur tous les sites. Aucune config requise. **Nécessite** que `PEXELS_API_KEY` soit set côté nous (déjà fait pour la prod).

### 2. Serper Images (Google Images)

API Serper : résultats Google Images réels.

- Plus de variété que Pexels
- **Attention licence** : Google Images contient des images sous copyright. À toi de vérifier la licence avant utilisation commerciale (filtre "Creative Commons" disponible).
- Stocké chez nous à l'insertion

À activer dans Site Settings → Images → "Use Serper for image search".

### 3. Génération IA

Crée une image custom à partir d'un prompt. Backend supporte DALL-E 3 (par défaut) et Stable Diffusion.

- Prompt : description de l'image en EN (les modèles d'image fonctionnent mieux en EN même si ton article est en FR)
- Style : photo réaliste / illustration / 3D / vector
- Aspect ratio : 1:1 / 16:9 / 9:16 / 4:3
- Coût : ~0.04$/image DALL-E 3, gratuit pour SD si self-hosted

Disponible sur les plans Pro et Agence. Désactivé en Solo et Free.

### 4. Upload manuel

Drag-drop ou click-to-upload depuis la galerie ou directement dans l'éditeur.

- Formats : JPG, PNG, WebP, GIF, SVG
- Taille max : 5 MB par image
- Compression auto en WebP côté nous (qualité 85, ~30 % de gain)
- Stocké sur Backblaze B2 + CDN Cloudflare

## Alt-text auto par IA

Quand tu insères une image (depuis n'importe quelle source), on génère automatiquement un alt-text :

- Modèle : Claude Sonnet voit l'image (vision) et écrit une description courte (15-25 mots)
- Inclut le **contexte de ton article** : le keyword cible, le sujet → l'alt-text est SEO-pertinent, pas juste descriptif
- Langue : matche celle de l'article (FR par défaut, EN/ES selon)
- Modifiable manuellement après insertion

Important pour le SEO : Google utilise l'alt-text pour Image Search + accessibilité (lecteurs d'écran).

## Optimisation auto

Toute image servie depuis notre infra (mode hébergé) ou stockée chez nous (autres modes) passe par :

- **Compression WebP** : 30-50 % de gain de poids vs JPG
- **Responsive `srcset`** : 3 tailles auto (mobile/tablet/desktop)
- **Lazy loading** : `loading="lazy"` natif sur toutes les images
- **CDN Cloudflare** : edge cache 30 jours

Score PageSpeed Insights de tes pages → +20-30 points si tu utilises notre stack vs un upload nu.

## OG image (partages sociaux)

L'image qui apparaît quand tu partages ton article sur Facebook / X / LinkedIn / Slack.

Configurable :
- **Per-article** : champ "Cover image" dans l'éditeur. Si présent, c'est l'OG image.
- **Site default** : Site Settings → Branding → "Image OG par défaut". Utilisée si l'article n'a pas de cover.

Format recommandé : 1200×630px. Plus petit = recoupé. Plus grand = recompressé (peut perdre en qualité).

L'OG image est injectée dans `<meta property="og:image" content="...">` automatiquement à la publication.

## Image SEO (suggestions)

**Articles → un article → Audit → onglet Images**

Pour chaque image dans l'article :
- Alt-text présent ?
- Alt-text contient le keyword cible ?
- Format (PNG/JPG/WebP) ?
- Taille de fichier raisonnable (< 200 KB recommandé) ?
- Dimensions cohérentes avec l'usage ?

Boutons :
- **Régénérer alt-text** (avec contexte SEO)
- **Compresser** (re-encode en WebP)
- **Resize** (génère 3 tailles responsive)

## Endpoints API

Pour l'automation :

| Endpoint | Méthode | Usage |
|---|---|---|
| `POST /api/upload-image/` | multipart/form-data | Upload une image |
| `GET /api/pexels/search/?query=...` | GET | Search Pexels |
| `GET /api/serper/images/?query=...` | GET | Search Google Images |
| `POST /api/generate-image/` | JSON `{prompt, style}` | IA gen |
| `GET /api/images/<uuid>/` | GET | Serve une image stockée |
| `POST /api/image-suggest/` | JSON `{image_url, context}` | Génère un alt-text |

Tous nécessitent JWT auth (pas l'API REST publique pour l'instant).

## Coûts

- **Pexels** : gratuit (10 000 req/mois sur leur plan free)
- **Serper Images** : compte dans ton quota Serper SERP (~0.005$/req)
- **DALL-E 3** : ~0.04$/image générée, facturé à nous puis répercuté en crédits IA
- **Upload + stockage** : inclus dans tous les plans (jusqu'à 1 GB/site, 10 GB Agence)

## Limites

- Pas d'éditeur d'image intégré (crop / filtres / texte sur image). Utilise Canva / Photopea avant upload.
- Pas de bibliothèque de templates / mockups pré-faits (sur la roadmap Q4 2026).
- Pas de watermarking automatique.

## Dépannage

| Erreur | Cause | Action |
|---|---|---|
| "PEXELS_API_KEY non configurée" | Env var manquante | Sur ta prod : ajouter la clé dans les env vars |
| "Image trop volumineuse" | > 5 MB | Compresser via TinyPNG ou Squoosh |
| Alt-text retourne vide | Vision API down ou rate limit | Réessaie. Si persistant, écris l'alt-text manuellement |
| Image n'apparaît pas dans Open Graph | Cover image manquant + pas de OG default | Ajoute une cover ou set un OG default |
