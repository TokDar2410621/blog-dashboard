# SEO Refactor Merge Plan

Base commit for all 12 branches: `f8f2ee2` (current `main` HEAD).
Every branch is a single commit on top of `main`, so each merge is one commit in, one commit out.

| Agent | Branch | Commit | Topic |
|-------|--------|--------|-------|
| 1  | `worktree-agent-ad177ccc` | `24a047b` | SEO scoring weights (2025 calibration) |
| 2  | `worktree-agent-a5d14651` | `909e90b` | Semantic keyword matching + `/seo-synonyms/` |
| 3  | `worktree-agent-a37a7295` | `86c0b40` | Backlinks via Serper (`/backlinks/`) |
| 4  | `worktree-agent-aeeeb37b` | `89182d5` | Competitor analysis (`/competitors/`) |
| 5  | `worktree-agent-a2bb868b` | `15d3cab` | Keyword research (`/keyword-research/`) |
| 6  | `worktree-agent-adec8563` | `632b27c` | Core Web Vitals / PageSpeed (`/page-speed/`) |
| 7  | `worktree-agent-a63fc3e3` | `a5b8b03` | Schema.org JSON-LD (`/seo-schema/`) |
| 8  | `worktree-agent-a3fc9dc6` | `f55584a` | Alt-text quality analysis |
| 9  | `worktree-agent-a5ff1fc4` | `e379b20` | Cannibalization detection (`/sites/.../cannibalization/`) |
| 10 | `worktree-agent-a6ef6c45` | `1ff1ed9` | Audit cache (1h TTL, hash keys) |
| 11 | `worktree-agent-a0dc6932` | `99e6508` | Google Search Console OAuth + migration |
| 12 | `worktree-agent-af4411df` | `456f451` | AI internal link suggestions (`/link-suggestions/`) |

## Conflict matrix

Rows = files touched by at least one agent. Columns = agents (1-12 as numbered above).

| File | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|------|---|---|---|---|---|---|---|---|---|----|----|----|
| `src/components/SEOAnalyzer.tsx`                | x | x | x | x | x | x | x | x | x |    | x  | x  |
| `backend/sites_mgmt/views.py`                   |   | x | x | x | x | x | x |   | x | x  | x  | x  |
| `backend/sites_mgmt/urls.py`                    |   | x | x | x | x | x | x |   | x | x  | x  | x  |
| `src/pages/dashboard/PostEditor.tsx`            |   |   | x |   |   |   | x |   | x |    | x  | x  |
| `backend/config/settings.py`                    |   |   |   |   |   |   |   |   |   | x  |    |    |
| `backend/requirements.txt`                      |   |   |   |   |   |   |   |   |   |    | x  |    |
| `backend/sites_mgmt/GSC_SETUP.md`               |   |   |   |   |   |   |   |   |   |    | x  |    |
| `backend/sites_mgmt/migrations/0007_...py`      |   |   |   |   |   |   |   |   |   |    | x  |    |
| `backend/sites_mgmt/models.py`                  |   |   |   |   |   |   |   |   |   |    | x  |    |
| `backend/sites_mgmt/serializers.py`             |   |   |   |   |   |   |   |   |   |    | x  |    |
| `src/lib/api-client.ts`                         |   |   |   |   |   |   |   |   |   |    | x  |    |
| `src/lib/schemas.ts`                            |   |   |   |   |   |   |   |   |   |    | x  |    |

**Hot files**:
- `SEOAnalyzer.tsx` - 11 of 12 agents
- `views.py` - 10 of 12
- `urls.py` - 10 of 12
- `PostEditor.tsx` - 5 of 12

### Conflict classification per hot file

#### `backend/sites_mgmt/urls.py` - **ADDITIVE with predictable textual collisions**

Every agent adds (a) one import name and (b) one `path(...)` entry.

| Agent | Import line added | URL path added | Hunk anchor |
|-------|-------------------|----------------|-------------|
| 2 a5d14651 | `SEOSynonymsView` | `seo-synonyms/` | after `seo-suggest/` (L34) |
| 3 a37a7295 | `BacklinksView` | `backlinks/` | after `seo-suggest/` (L34) |
| 4 aeeeb37b | `CompetitorAnalysisView` | `competitors/` | after `seo-suggest/` (L34) |
| 5 a2bb868b | `KeywordResearchView` | `keyword-research/` | after `seo-suggest/` (L34) |
| 6 adec8563 | `PageSpeedView` | `page-speed/` | after `seo-suggest/` (L34) |
| 7 a63fc3e3 | `SEOSchemaView` | `seo-schema/` | after `seo-suggest/` (L34) |
| 9 a5ff1fc4 | `SiteCannibalizationView` | `sites/<id>/cannibalization/` | after `site-tags` (L22) |
| 10 a6ef6c45 | `SEOCacheClearView` | `seo-cache/clear/` | after `seo-suggest/` (L34) |
| 11 a0dc6932 | `GSC*View` (3) | `sites/<id>/gsc/*` (3) | after `seo-suggest/` (L34) |
| 12 af4411df | `LinkSuggestionsView` | `sites/<id>/link-suggestions/` | after `generate-inline/` (L24) |

These are all pure insertions at nearby lines. A 3-way merge will mark conflicts for 8 of them because they all insert after the exact same anchor line, but **every resolution is mechanical**: keep all new imports, keep all new `path(...)` lines. No two agents define the same view name or URL path.

#### `backend/sites_mgmt/views.py` - **MOSTLY ADDITIVE (class-level appends) + ONE invasive editor**

Two insertion clusters:
- **Cluster A - after `SEOSuggestView` (~L1251)**: agents 2, 3, 5, 6, 7, 12 each append one new `*View` class.
- **Cluster B - after `SEOFixView` (~L1337)**: agent 4 (competitor analysis).
- **Cluster C - end of file (L1526)**: agent 11 (GSC views, 288 lines).
- **Cluster D - after `SitePostDetailView` (~L420)**: agent 9 (cannibalization).

The one **invasive** editor is **Agent 10 (`a6ef6c45` / caching)**: it edits in-place inside `GenerateTagsView`, `SEOAuditView`, `SEOFixView`, `SEOSuggestView` to wrap each `return Response(...)` with `cache.get/set` + `X-Cache` headers. It also adds `import hashlib` and `from django.core.cache import cache` to the top imports.

Because the caching agent edits *existing* lines, its conflict risk with the other appends depends on whether the 3-way merge anchors the new classes before or after its edits. In practice:
- Caching changes are **before** line 1251 - so appending new classes at 1251+ does **not** collide with caching's modified regions.
- Competitor analysis at 1337 is also past caching's last edit (~L1282). Safe.

Imports: only agents 6 (`urllib.parse.quote`) and 10 (`hashlib`, `django.core.cache.cache`) edit the imports block, and they add different lines. No conflict.

**Verdict**: views.py can be merged cleanly in order, with the expected textual conflicts at the 1251 anchor resolved by "keep both sides" for each pair.

#### `src/components/SEOAnalyzer.tsx` - **THE BIGGEST CONFLICT ZONE**

Distinct hunk types by agent:

| Agent | Imports (L1-14) | Props interface (L22-32) | Destructured props (L82) | State/handlers (L101) | In-`useMemo` check edits (L150-400) | New JSX card (L478-766) |
|-------|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 ad177ccc scoring       |  |  |  |  | **EDITS** score numbers in ~18 existing hunks |  |
| 2 a5d14651 synonyms      | x |  |  | x | **EDITS** keyword match logic + deps |  |
| 3 a37a7295 backlinks     | x | x | x | x | new guard hunk | x |
| 4 aeeeb37b competitors   | x |  |  | x | new guard hunk | x |
| 5 a2bb868b kw research   | x | x |  | x | new guard hunk | x |
| 6 adec8563 pagespeed     | x | x | x | x | new guard hunk | x |
| 7 a63fc3e3 schema        | x | x | x | x | new guard hunk | x |
| 8 a3fc9dc6 alt-text      |  |  |  |  | **REWRITES** `countImages` → `analyzeAltTexts`, replaces the image-check branch in `useMemo` (~L370) |  |
| 9 a5ff1fc4 cannibal      | x | x | x | x | new guard hunk | x |
| 11 a0dc6932 GSC          | x | x | x | x |  | x |
| 12 af4411df link-sugg    | x | x | x | x | new guard hunk | x |

**Additive group** (agents 3, 4, 5, 6, 7, 9, 11, 12): each adds a new import icon, new optional prop to `SEOAnalyzerProps`, new destructuring entry, new React state + async handler, and one new `<Card>` block in the JSX tail. Conflicts here are textual (same anchors L11, L22, L82, L101, L478/L766) but **semantically additive** - resolutions are mechanical.

**Competing edits** (agents 1, 2, 8): modify the same pre-existing logic inside `useMemo`:
- Agent **1 (scoring)** changes dozens of `score: N` literals across image, word-count, meta, title, links, slug checks - and adds a long JSDoc header at L103.
- Agent **2 (synonyms)** rewrites the `keyword.trim()` branch (L207-220 base) to call `containsWholeWord(terms, ...)` and adds `synonyms` to the deps array.
- Agent **8 (alt-text)** replaces the whole `countImages` helper with `analyzeAltTexts`, and the `if (images.total > 0 && images.withAlt === images.total)` branch around base L299 becomes three new branches.

Agents 1, 2 and 8 touch different check branches, so they do NOT textually collide with each other, but:
- Agent 1 and Agent 8 both change the `score:` values on the images check → **real competing conflict**. Agent 1 sets images `good` = 8, Agent 8 sets `good` = 15.
- Agent 1 and Agent 2 both change the `score:` values on the keyword branch → **real competing conflict**. Resolution: keep Agent 2's new logic, keep Agent 1's new weights (score numbers).

#### `src/pages/dashboard/PostEditor.tsx` - **ADDITIVE with one duplicate-prop collision**

All 5 touching agents insert new JSX props right after `keyword={tagsInput.split(",")[0]?.trim() || ""}` (L672).

- Agent 3 (backlinks): adds `articleUrl={...blog/${postSlug}}` (slash-blog form).
- Agent 7 (schema): adds `author`, `publishedAt`, `siteDomain`, `language`.
- Agent 9 (cannibalization): adds `siteId={...}`, `currentSlug={postSlug}`.
- Agent 11 (GSC): adds `siteId={...}`, `articleUrl={...${postSlug}/}` (trailing-slash form).
- Agent 12 (link suggestions): adds `siteId={...}`, `currentSlug={slug}` (URL-param!).

**Real competing edits**:
- `siteId` defined three times - keep one. All three use the same expression `siteId ? Number(siteId) : undefined`, so dedup is trivial.
- `articleUrl` defined two different ways (Agent 3: `/blog/${postSlug}`; Agent 11: `${postSlug}/`). Pick one canonical URL builder based on how blog URLs are actually served in production.
- `currentSlug` defined two ways - Agent 9 uses `postSlug` (local form state), Agent 12 uses `slug` (URL route param, the original slug). **Semantic difference**. Agent 9's `postSlug` is correct for self-cannibalization detection (match what user is *currently typing*); Agent 12's `slug` is the pre-edit slug. Recommended: use `postSlug` for both.

## Recommended merge order

Guiding principle: least invasive first → most invasive last, and merge the `SEOAnalyzer.tsx` competing editors (1, 2, 8) **before** the additive JSX-card cluster so their score/logic edits apply cleanly before the card additions rebase them.

### Phase 0 - prep

```bash
git checkout main
git pull --ff-only
git switch -c seo-refactor-merge
```

Do all work on the integration branch, not directly on `main`. Only fast-forward `main` once the whole stack is green.

### Phase 1 - self-contained SEOAnalyzer editors (no backend, no urls.py)

These three agents rewrite existing logic only. Merging them first produces the smallest conflict surface for the rest.

1. **Agent 1 - scoring weights** (fewest files, pure number edits)
   ```bash
   git merge --no-ff worktree-agent-ad177ccc
   ```
   Expected: **clean**.

2. **Agent 8 - alt-text quality**
   ```bash
   git merge --no-ff worktree-agent-a3fc9dc6
   ```
   Expected: **one conflict** with Agent 1 in `SEOAnalyzer.tsx` around the images check (`score: 15` vs `score: 8`). See resolution hint below.

3. **Agent 2 - semantic keyword matching** (also adds `/seo-synonyms/` backend endpoint)
   ```bash
   git merge --no-ff worktree-agent-a5d14651
   ```
   Expected: **conflict** with Agent 1 on keyword-check branch `score:` values (Agent 2 replaced the body, Agent 1 changed the scores). Keep Agent 2's new regex-based body, apply Agent 1's updated `score` literals to Agent 2's new push calls.

### Phase 2 - additive backend-only feature (cache is cross-cutting)

4. **Agent 10 - caching** (invasive inside existing views but no SEOAnalyzer.tsx)
   ```bash
   git merge --no-ff worktree-agent-a6ef6c45
   ```
   Expected: **clean** (no other agent has landed in Phases 1-2 that touches views.py).
   Why early: once cache wrappers are in the 4 existing SEO views, every later agent that adds new endpoints slots in cleanly at the class-level without needing to interleave with cache logic.

### Phase 3 - additive feature agents with SEOAnalyzer Card + endpoint + (maybe) PostEditor prop

Order within this phase is by size of PostEditor touch (smallest first), then alphabetical.

5. **Agent 4 - competitor analysis** (no PostEditor)
   ```bash
   git merge --no-ff worktree-agent-aeeeb37b
   ```
   Expected: `SEOAnalyzer.tsx` import-line + JSX-tail conflicts with Phase-1 merges. All additive.

6. **Agent 5 - keyword research** (no PostEditor)
   ```bash
   git merge --no-ff worktree-agent-a2bb868b
   ```
   Expected: `urls.py` import/path line, `views.py` 1251 anchor, `SEOAnalyzer.tsx` import + state + JSX tail conflicts. Keep both.

7. **Agent 6 - PageSpeed** (no PostEditor)
   ```bash
   git merge --no-ff worktree-agent-adec8563
   ```
   Expected: similar additive conflicts. Plus `urllib.parse.quote` import in views.py (unique, no collision).

8. **Agent 9 - cannibalization** (touches PostEditor)
   ```bash
   git merge --no-ff worktree-agent-a5ff1fc4
   ```
   Expected: additive `urls.py`, `views.py` (L420 anchor - no collision), `SEOAnalyzer.tsx`, plus first PostEditor prop insertion (clean since no other agent has added props yet).

9. **Agent 12 - AI link suggestions** (touches PostEditor)
   ```bash
   git merge --no-ff worktree-agent-af4411df
   ```
   Expected: **PostEditor prop collision** with Agent 9 (duplicate `siteId`, different `currentSlug`). See resolution hint below.

10. **Agent 3 - backlinks** (touches PostEditor)
    ```bash
    git merge --no-ff worktree-agent-a37a7295
    ```
    Expected: **PostEditor prop collision** on `siteId`, adds `articleUrl` (slash-blog form).

11. **Agent 7 - schema.org** (touches PostEditor)
    ```bash
    git merge --no-ff worktree-agent-a63fc3e3
    ```
    Expected: PostEditor additive (author/publishedAt/siteDomain/language - no collision with prior), SEOAnalyzer Card additive.

### Phase 4 - the big one

12. **Agent 11 - Google Search Console** (most files, touches migration, models, serializers, api-client, schemas, PostEditor, SEOAnalyzer)
    ```bash
    git merge --no-ff worktree-agent-a0dc6932
    ```
    Expected:
    - `urls.py`: additive (3 new paths, 3 new imports).
    - `views.py`: appended at end of file - **clean** (nothing else there).
    - `SEOAnalyzer.tsx`: all six anchors collide additively with the rest of the accumulated merges.
    - `PostEditor.tsx`: `siteId` already there from prior merges - delete Agent 11's duplicate. `articleUrl` collides with Agent 3 - pick one URL scheme.
    - `src/lib/api-client.ts`, `src/lib/schemas.ts`: clean.
    - Migration `0007_site_gsc_*.py`: new file, clean.
    - `backend/requirements.txt`: appended, clean.

### Final verification

```bash
git diff main..seo-refactor-merge --stat
cd backend && python manage.py makemigrations --check --dry-run
cd .. && npm ci && npm run build
# run backend + frontend tests if available
```

Only after all 12 merges pass tests:
```bash
git checkout main
git merge --ff-only seo-refactor-merge
```

## Manual conflict resolution hints

### Hint 1 - `SEOAnalyzer.tsx`: Agent 1 (scoring) × Agent 8 (alt-text)
Agent 1 edits `score:` literals on the old `countImages`-based branches. Agent 8 replaces those branches entirely with three new `analyzeAltTexts` branches. **Merge rule**: discard Agent 1's literal edits in the image branches and re-apply Agent 1's intended new weights to Agent 8's new branches (`score: 15` for all-quality-good, `score: 8` for warning, `score: 2` for all-bad, `score: 3` for no-images). The weight totals in Agent 1's rationale comment must still sum to 100 - update that comment if necessary.

### Hint 2 - `SEOAnalyzer.tsx`: Agent 1 × Agent 2 (synonyms)
Agent 2 replaces the keyword-check branch (`const kw = normalize(keyword); const titleHit = ...`) with a `containsWholeWord(terms, ...)` version. Agent 1 edits only the `score:` values on the three push calls inside that branch. **Merge rule**: take Agent 2's new body verbatim, then overwrite the `score:` values in its three push calls with Agent 1's new values. Also add `synonyms` to the `useMemo` deps array (Agent 2 did this; keep it).

### Hint 3 - `SEOAnalyzer.tsx`: useMemo deps array
Several agents append new state variables to the deps array at the end of `useMemo`. When resolving, concatenate the unique names: `[title, excerpt, content, slug, coverImage, keyword, synonyms, i18n.language]` plus whatever additional state each additive agent introduced (none of the additive agents actually put anything into the **scoring** useMemo - their new state is read in separate effects/render blocks - so the only net addition to the deps array is `synonyms` from Agent 2).

### Hint 4 - `SEOAnalyzer.tsx`: JSX tail cards
Agents 3, 4, 5, 6, 7, 9, 11, 12 each append a new `<Card>` near the end of the component return. Order them in a consistent UX grouping (recommended): Keyword Research → Competitors → PageSpeed → Backlinks → Cannibalization → Link Suggestions → Schema.org → GSC queries. Each card is self-contained; just keep them all.

### Hint 5 - `PostEditor.tsx`: deduplicate `siteId`
Agents 9, 11, 12 all emit `siteId={siteId ? Number(siteId) : undefined}`. Keep one.

### Hint 6 - `PostEditor.tsx`: pick one `articleUrl`
Agent 3: `https://${currentSite.domain.replace(/^https?:\/\//, "").replace(/\/$/, "")}/blog/${postSlug}`
Agent 11: `${currentSite.domain.replace(/\/$/, "")}/${postSlug}/`

These are materially different URL schemes. Check how live blog URLs are actually served (look at `PublicPostDetailView` routing) and pick whichever matches. **Most likely Agent 3's `/blog/${slug}` is correct** given it forces HTTPS and strips the scheme from user-entered domains. Use that single value for both backlinks and GSC queries.

### Hint 7 - `PostEditor.tsx`: `currentSlug` - use `postSlug`
Agent 9 passes `postSlug` (current form state). Agent 12 passes `slug` (URL route param from `useParams`). For self-exclusion in cannibalization / link-suggestion queries, use `postSlug` so renames are detected as the user types. Change Agent 12's prop to `postSlug` at merge time.

### Hint 8 - `urls.py` and `views.py` anchor collisions
For every expected 3-way conflict on `urls.py` around the `seo-suggest/` path line and views.py around line 1251: the correct resolution is always "keep both sides, preserve the new class/path ordering they arrive in." Use `git merge -X patience` for these commits if the default recursive strategy mis-aligns the hunks.

## Risks & watch-outs

- **Migration ordering (Agent 11)**. The GSC migration is named `0007_site_gsc_property_url_site_gsc_refresh_token`. Verify that `0006_*` exists on `main` before merging, and that no other worktree added a sibling `0007_*` (none of the other 11 did - confirmed).
- **`requirements.txt` (Agent 11)** adds 3 packages for GSC OAuth. Re-run `pip install -r backend/requirements.txt` and `python manage.py migrate` immediately after the Agent 11 merge.
- **Environment variables**. Agents depend on: `SERPER_API_KEY` (agents 3, 4, 5), `GEMINI_API_KEY` (agents 2, 5, 7, 10, 12), Google PageSpeed key (agent 6), Google OAuth client id/secret + redirect URI (agent 11). Update `.env.example` after the final merge; all endpoints are coded to return graceful fallbacks when the key is missing, so dev won't crash.
- **LocMemCache is per-process (Agent 10)**. In a multi-worker gunicorn deploy the 1h cache won't be shared across workers; either bump to Redis in settings, or accept up-to-W-fold cache churn (where W = worker count).
- **Keyword-check score double-count**. After Phases 1 + 3 land, verify that the `max-score` accumulator used to compute the 0-100 total doesn't drift. Agent 1 recalibrated it to sum to 100 exactly; new cards added in Phase 3 are rendered **outside** the score useMemo (they're separate async AI panels), so they don't poison the total. Double-check this after merge by computing `checks.reduce((s,c) => s + c.score, 0)` on a good-state article.
- **`postSlug` vs `slug`** (see Hint 7). Easy to overlook in a `-X ours`/`-X theirs` automatic resolution. Do a manual grep after Phase 4:
  ```
  rg "currentSlug=\{slug\}" src/pages/dashboard/PostEditor.tsx
  ```
  should return zero hits.
- **No agent touched the test suite**. There are no new unit tests for any of the 12 features. Budget time post-merge to add at least one smoke test per endpoint.
- **`SEOAnalyzer.tsx` will exceed ~1500 LOC after the full merge**. Consider a follow-up refactor to split it into `SEOAnalyzer/score.ts`, `SEOAnalyzer/cards/*.tsx` once the merge is green. Do not attempt this refactor during the merge itself.
- **PostEditor prop-order dependence**: if any of the new agents relied on the prop being rendered before `onApplyFix`, double-check the manually merged order of `siteId`, `articleUrl`, `currentSlug`, `author`, `publishedAt`, `siteDomain`, `language` - React does not care about prop ordering, but a merge can silently drop a prop if conflict markers are edited carelessly. Compare the final `<SEOAnalyzer ... />` call site against each agent's diff one last time before committing.
- **Agent 10 cache key for audit view does not include the `keyword`**. Verify this post-merge; if the audit prompt depends on `keyword`, the cache key must hash it, otherwise stale responses will be served when the user changes the target keyword.
- **`f8f2ee2` is also the last commit on main**. If any fix is pushed to `main` between now and merge completion, rebase the integration branch onto the new main before continuing - do NOT try to merge new-main into the integration branch midway.
