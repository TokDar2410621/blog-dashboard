# Éditeur d'articles (écriture manuelle)

L'IA génère, mais tu peux aussi écrire **à la main** ou éditer un article généré pour le corriger / l'enrichir. L'éditeur est accessible depuis :

- **Articles → Nouvel article** (création vierge)
- **Articles → un article existant → Modifier** (édition)
- Direct URL : `/dashboard/<id>/articles/nouveau` ou `/dashboard/<id>/articles/<slug>`

## Vue d'ensemble

L'éditeur est un éditeur Markdown / WYSIWYG hybride avec :

- **Panneau gauche** : champs structurels (titre, slug, langue, statut, catégorie, tags, cover image)
- **Panneau central** : zone d'écriture Markdown avec aperçu live
- **Panneau droit** : outils contextuels (audit SEO, brief de contenu, suggestions de liens, lexique)

Tout est sauvegardé automatiquement (auto-save toutes les 5 sec après inactivité). Indicateur en bas : "Sauvegardé · il y a 2 sec".

## Workflow recommandé

### Cas 1 - Réviser un article généré par l'IA

1. Article généré apparaît dans Articles
2. Clique pour ouvrir → tu vois le contenu complet
3. Lis-le rapidement (5-10 min) pour repérer :
   - Stats / chiffres à vérifier (l'IA peut halluciner)
   - Ton qui sonne pas naturel pour ta marque
   - Liens internes à compléter
4. Édite directement dans l'éditeur (Markdown ou WYSIWYG)
5. **Audit** dans le panneau droit pour score à jour
6. **Publier** quand satisfait (statut Brouillon → Publié)

### Cas 2 - Écrire de zéro

1. Articles → **Nouvel article**
2. Tape ton titre → on génère un slug auto (modifiable)
3. Choisis la langue (FR/EN/ES selon ton site)
4. Écris ton contenu en Markdown
5. **Inline AI assist** : sélectionne un paragraphe → bouton "Améliorer avec IA" → l'IA reformule sans changer le sens
6. **Brief de contenu** dans le panneau droit pour structurer ton plan
7. Audit + Publier

### Cas 3 - Importer du contenu existant

Pas d'import direct via UI pour l'instant. 2 options :

- **Copier-coller** : copie le contenu depuis Word/Notion/Docs → colle dans l'éditeur (le formatage Markdown se préserve via Turndown).
- **Via l'API** : `POST /api/v1/sites/<id>/articles/` avec `{title, content, slug}`.

## Champs obligatoires

| Champ | Requis | Note |
|---|---|---|
| Titre | ✅ | Max 200 caractères. SEO : 50-60 idéal |
| Slug | ✅ | Auto-généré depuis le titre. Modifiable. URL-safe |
| Contenu | ✅ | Markdown |
| Langue | ✅ | FR / EN / ES selon ce qui est activé sur le site |
| Statut | ✅ | Brouillon / Programmé / Publié |

## Champs optionnels (mais recommandés)

| Champ | Effet SEO |
|---|---|
| Excerpt | Apparaît dans Open Graph + listings. 140-155 caractères idéal |
| Cover image | Open Graph image + image en haut de l'article |
| Catégorie | Hiérarchise tes articles. Une seule catégorie par article |
| Tags | Multiples. Apparaissent en bas de l'article + permettent le maillage |
| Auteur | Hérite du `default_author` du site, modifiable per-article |
| Reading time | Auto-calculé depuis le nombre de mots |
| Featured | Met en avant sur la home du blog public |

## Brouillon, Programmé, Publié

- **Brouillon** : invisible publiquement. Indéfini jusqu'à ce que tu le publies.
- **Programmé** : `scheduled_at` fixe une date future. Une commande Django (`python manage.py publish_scheduled`) tourne toutes les 15 min et passe en `Publié` à l'heure dite.
- **Publié** : visible publiquement. Si tu changes le slug, on crée automatiquement une [Redirection 301](seo-tools.md#redirections-301) depuis l'ancien.

## Markdown supporté

GitHub Flavored Markdown (GFM) :

- Headings `#` `##` `###`
- Listes (numérotées et non)
- Tables
- Blocs de code avec syntax highlighting (langues : js, ts, py, html, css, sql, bash, json...)
- Liens et images
- Strikethrough `~~text~~`
- Tâches `[ ]` / `[x]`
- HTML inline (utilisé avec parcimonie, l'audit SEO peut alerter)

Conversion auto en HTML à la publication via `markdown` Python (extensions: extra, tables, fenced_code).

## Insertion d'images

3 sources, accessibles via le bouton "Image" dans la toolbar :

1. **Pexels** : search free stock photos, license CC0
2. **Serper Images** : Google Images (vérifier les droits d'auteur côté toi)
3. **Génération IA** : prompt → image générée (DALL-E, Stable Diffusion selon config)
4. **Upload manuel** : drag-drop un fichier (max 5 MB, formats JPG/PNG/WebP/GIF)

L'alt-text est généré automatiquement par l'IA quand tu insères une image (description accessibilité + SEO).

Détails complets : [Gestion des images](images.md).

## Outils contextuels (panneau droit)

### Audit SEO

Score 0-100 + checklist détaillée. Bouton **Corriger automatiquement** applique les fixes simples (title trop long, méta manquante, schema absent).

### Brief de contenu

Génère un plan stratégique pour ton mot-clé cible. Apparaît avant que tu commences à écrire.

### Suggestions de liens internes

Détecte les opportunités de maillage : tes articles existants qui pourraient être liés depuis ce contenu. Clique pour insérer.

### Lexique FR-CA

Pour les articles en FR : flag les termes France (shopping, week-end, parking...) et propose les équivalents québécois.

### Vérification plagiat

Originality.ai sur ton contenu. Score d'originalité + AI-detection. Coût ~0.01$/1k mots. Désactivable dans Site Settings.

### Synonymes SEO

Sélectionne un mot → suggestions de synonymes pour éviter la sur-optimisation (over-keyword stuffing). Préserve le sens.

### Readability

Score Flesch (français : Kandel-Moles). Indique si ton article est trop technique pour son audience.

## Raccourcis clavier

| Raccourci | Action |
|---|---|
| `Cmd/Ctrl+S` | Force-save |
| `Cmd/Ctrl+B` | Bold |
| `Cmd/Ctrl+I` | Italic |
| `Cmd/Ctrl+K` | Insérer lien |
| `Cmd/Ctrl+Shift+P` | Toggle preview Markdown |
| `Cmd/Ctrl+Enter` | Publier (si Brouillon) |

## Limites

- Pas de collaboratif temps-réel (pas de Google-Docs-style multi-curseur). Si 2 personnes éditent en même temps, le dernier save écrase.
- Pas de versioning (pour l'instant). Une fois publié, plus de rollback. Sauvegarde manuellement avant un gros changement.
- Pas d'import direct depuis WordPress XML / Markdown ZIP. Faisable via l'API (`POST /articles/` en boucle) avec un script.

## Dépannage

| Problème | Cause | Action |
|---|---|---|
| L'article ne sauvegarde pas | Connexion ou token JWT expiré | Refresh la page, re-login si nécessaire |
| Le slug change tout seul | Auto-slug-from-title actif | Désactive dans Site Settings → Editor → "Lock slug after first save" |
| L'audit reste en "calcul" | Timeout backend | Recharge la page. Si récurrent : signale via support |
| L'image ne s'upload pas | Fichier > 5 MB ou format non supporté | Compresse l'image (TinyPNG, Squoosh) ou convertis en JPG/WebP |
