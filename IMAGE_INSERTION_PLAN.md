# Plan d'insertion d'image flexible - blog-dashboard

## Endroits supportant l'insertion

Déjà couverts :
- Contenu markdown (toolbar + ImageInsertDialog + drag-drop textarea)
- Image de couverture (Pexels / Serper / AI dans Settings)
- Remplacement via clic preview

À ajouter :
- Drag-drop global avec détection target (cover vs contenu)
- Paste clipboard (Ctrl+V screenshot)
- Slash command `/image` inline
- Raccourci `Ctrl+Shift+I`
- Bouton `+` flottant entre paragraphes (style Notion)

## Méthodes (unifier via dialogue 6 onglets)

1. Upload local (existe)
2. URL externe (nouveau)
3. Pexels (existe)
4. Google/Serper (migrer depuis cover)
5. AI Generate (migrer depuis cover)
6. Bibliothèque (nouveau - `GET /api/uploaded-images/`)

## UX

- Dialogue unifié `ImageInsertDialog` avec prop `mode: 'inline' | 'cover' | 'replace'`
- Preview avant insertion : alt, caption, alignment (left/center/right), width (small/medium/full)
- Hover image : overlay Edit/Replace/Delete/Align
- Génère markdown étendu `![alt](url "caption")` ou HTML `<figure class="align-center size-medium">`

## Phase 1 - Fondation (FOCUS)

### Nouveaux fichiers

- `src/components/image-insert/ImageInsertDialog.tsx` (refactor avec onglets)
- `src/components/image-insert/tabs/UploadTab.tsx`
- `src/components/image-insert/tabs/UrlTab.tsx`
- `src/components/image-insert/tabs/PexelsTab.tsx`
- `src/components/image-insert/tabs/SerperTab.tsx`
- `src/components/image-insert/tabs/AiTab.tsx`
- `src/components/image-insert/tabs/LibraryTab.tsx`
- `src/components/image-insert/ImagePreviewCard.tsx` (alt + caption + alignment + width)
- `src/hooks/useImageInsertion.ts` (state centralisé)
- `src/lib/image-markdown.ts` (helpers `buildImageMarkup()`)

### Backend

- `GET /api/uploaded-images/?limit=50` → liste paginée `UploadedImage` de l'utilisateur
- `DELETE /api/uploaded-images/<id>/` (avec check ownership)

### Frontend modifs

- `src/lib/api-client.ts` : `listUploadedImages()`, `deleteUploadedImage(id)`
- `src/pages/dashboard/PostEditor.tsx` : remplacer state cover dupliqué par appel au dialogue en `mode="cover"`. Supprimer la grosse section cover inline → bouton "Modifier l'image de couverture"

### État dans `useImageInsertion`

```ts
{
  dialogOpen: boolean
  dialogMode: 'inline' | 'cover' | 'replace'
  cursorPos: number
  replacingSrc: string | null
  initialQuery: string
  selectedTab: 'upload' | 'url' | 'pexels' | 'serper' | 'ai' | 'library'
  selectedImage: { url, alt, caption, alignment, width } | null
}
```

## Phase 2 - Paste + drop global (après Phase 1)

- Hook `useClipboardImage`
- Listener paste sur textarea MarkdownEditor
- Composant `GlobalDropZone` wrappant PostEditor avec 2 zones visibles
- Raccourci `Ctrl+Shift+I` dans PostEditor

## Phase 3 - Slash command + bouton `+` flottant

- `SlashCommandMenu` popover
- Détection `/` dans MarkdownEditor + positionnement
- `FloatingAddButton` sur ligne courante
- Navigation clavier ↑↓ Enter Esc

## Phase 4 - Simplification + preview interactive

- Section cover inline remplacée par bouton simple
- Overlay hover sur images preview (Edit/Replace/Delete/Align)
- Support HTML `<figure>` preview + Turndown bidirectionnel

## Phase 5 - Polish

- Validation taille/format client
- Proxy-download URLs externes
- Progress bar uploads multi
- i18n complet
- Tests Playwright
- Accessibility ARIA

## Edge cases à couvrir

- Fichier > 5MB → compression `browser-image-compression`
- GIF animé → badge + warning si > 2MB
- HEIC/BMP/TIFF → rejet avec message clair
- URL externe invalide → HEAD request + fallback onError
- CORS-blocked → proposer proxy-download
- Paste d'URL texte → proposer insertion OU téléchargement
- Drop multi-fichiers → upload séquentiel + progress
- Rollback placeholder si upload échoue
- Alt vide → fallback filename, warning SEO
- Mobile touch → drag-drop non supporté, fallback toolbar
