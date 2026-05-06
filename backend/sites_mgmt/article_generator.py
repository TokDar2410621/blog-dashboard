# -*- coding: utf-8 -*-
"""
Article Generator for multi-site blog dashboard.
Ported from the portfolio's generate_article management command.
All DB queries use .using(alias) for dynamic site connections.
"""

import os
import json
import re
import random
import requests
from datetime import date
from django.utils.text import slugify
from blog.models import BlogPost, Category, Tag


# === AI LOGOS ===
AI_LOGOS = {
    'openai': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/OpenAI_Logo.svg/1024px-OpenAI_Logo.svg.png',
    'chatgpt': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/ChatGPT_logo.svg/1024px-ChatGPT_logo.svg.png',
    'gpt': 'https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/ChatGPT_logo.svg/1024px-ChatGPT_logo.svg.png',
    'claude': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Anthropic_logo.svg/1024px-Anthropic_logo.svg.png',
    'anthropic': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/78/Anthropic_logo.svg/1024px-Anthropic_logo.svg.png',
    'gemini': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Google_Gemini_logo.svg/1024px-Google_Gemini_logo.svg.png',
    'google ai': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Google_Gemini_logo.svg/1024px-Google_Gemini_logo.svg.png',
    'midjourney': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Midjourney_Emblem.png/600px-Midjourney_Emblem.png',
    'stable diffusion': 'https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/Stability_AI_logo.svg/1024px-Stability_AI_logo.svg.png',
    'dall-e': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/OpenAI_Logo.svg/1024px-OpenAI_Logo.svg.png',
    'copilot': 'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/GitHub_Copilot_logo.svg/1024px-GitHub_Copilot_logo.svg.png',
    'github': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Octicons-mark-github.svg/1024px-Octicons-mark-github.svg.png',
    'meta': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/1024px-Meta_Platforms_Inc._logo.svg.png',
    'llama': 'https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Meta_Platforms_Inc._logo.svg/1024px-Meta_Platforms_Inc._logo.svg.png',
    'mistral': 'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e6/Mistral_AI_logo.svg/1024px-Mistral_AI_logo.svg.png',
    'perplexity': 'https://upload.wikimedia.org/wikipedia/commons/1/1d/Perplexity_AI_logo.png',
    'cursor': 'https://www.cursor.com/brand/icon.svg',
    'nvidia': 'https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Nvidia_logo.svg/1024px-Nvidia_logo.svg.png',
    'microsoft': 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/Microsoft_logo.svg/1024px-Microsoft_logo.svg.png',
    'hugging face': 'https://huggingface.co/front/assets/huggingface_logo.svg',
    'huggingface': 'https://huggingface.co/front/assets/huggingface_logo.svg',
}

LENGTH_CONFIG = {
    'short': {'words': '800-1200', 'images': 2, 'sections': '2-3', 'tokens': 4000},
    'medium': {'words': '1500-2000', 'images': 3, 'sections': '3-4', 'tokens': 6000},
    'long': {'words': '2500-3500', 'images': 5, 'sections': '5-7', 'tokens': 10000},
}

# Evergreen topics for auto-selection
PILLAR_TOPICS = [
    'comment construire un MVP rapidement startup',
    'valider une idee SaaS avant de coder',
    'pourquoi startups echouent erreurs courantes',
    'generer du trafic organique sans publicite',
    'SEO programmatique strategie contenu',
    'construire un side project rentable',
]

STRATEGY_TOPICS = [
    'penser produit comme une machine systeme',
    'mauvaises metriques startup vanity metrics',
    'perfectionnisme ennemi du lancement produit',
    'blogging traditionnel vs SEO programmatique',
    'construire en public build in public avantages',
    'monetiser un side project developer',
    'choisir sa niche marche SaaS',
    'product market fit comment savoir',
    'acquisition utilisateurs bootstrap startup',
    'pricing strategie SaaS freelance',
]

LESSONS_TOPICS = [
    'erreurs premier projet SaaS lecons',
    'ce que j ai appris en lancant un produit',
    'echecs startup ce qu on ne dit pas',
    'mythes entrepreneuriat realite terrain',
    'solo founder avantages inconvenients',
    'burnout developpeur side project equilibre',
    'quand pivoter abandonner projet',
    'feedback utilisateurs comment collecter',
]

RESOURCES_TOPICS = [
    'stack technique ideal side project 2025',
    'outils no code low code developpeur',
    'automatiser taches repetitives developpeur',
    'productivite developpeur deep work',
    'gerer son temps side project travail',
    'apprendre en construisant learn by building',
]

TYPE_INSTRUCTIONS = {
    'news': """
**Type: Article d'opinion**
- Commence par une accroche personnelle (anecdote, constat, frustration)
- Developpe ton argument principal avec des exemples
- Anticipe et reponds aux objections
- Conclus avec une prise de position claire""",
    'tutorial': """
**Type: Guide pratique**
- Introduction: pourquoi ce sujet compte pour toi
- Etapes basees sur ton experience reelle
- Erreurs que TU as faites (et comment les eviter)
- Resultats concrets que tu as obtenus""",
    'comparison': """
**Type: Analyse comparative**
- Ton experience avec chaque option
- Ce qui a marche / pas marche pour TOI
- Recommandation claire basee sur ton cas d'usage
- Pas de "ca depend" - donne ton avis""",
    'guide': """
**Type: Reflexion approfondie**
- Partage ta vision et philosophie sur le sujet
- Exemples de ton parcours entrepreneurial
- Lecons contre-intuitives que tu as apprises
- Conseils que tu aurais aime recevoir plus tot""",
    'review': """
**Type: Retour d'experience**
- Contexte: pourquoi tu as essaye ca
- Ce qui s'est passe (bon et mauvais)
- Ce que tu ferais differemment
- Verdict honnete et sans filtre""",
    'story': """
**Type: Histoire / Recit personnel**

STRUCTURE NARRATIVE OBLIGATOIRE:
1. **Accroche captivante** - Commence IN MEDIAS RES
2. **Contexte & Setup** (10-15%)
3. **Le conflit / La lutte** (40-50%) - Details concrets, emotions, dialogues
4. **Le tournant / La revelation** (15-20%)
5. **La resolution & Lecon** (15-20%)

TECHNIQUES: Show don't tell, details sensoriels, dialogues, suspense, humour, vulnerabilite.
TON: Comme si tu racontais a un ami autour d'une biere.""",
    'local': """
**Type: Guide/Annuaire Local**

STRUCTURE OBLIGATOIRE:
1. Introduction sur le secteur dans cette region
2. Liste des entreprises trouvees (avec liens cliquables)
3. Comment choisir un prestataire
4. Conclusion

REGLES: Inclure TOUS les sites web trouves, liens cliquables [Nom](URL), ne pas inventer."""
}


class ArticleGenerator:
    """Generates articles for a specific site using dynamic DB connections."""

    def __init__(self, alias, knowledge_base='', wp_site=None, shopify_site=None,
                 webflow_site=None):
        """alias: Django DB alias for external Postgres mode (None for WP/hosted/Shopify/Webflow).
        wp_site: Site model instance when the site is in WordPress mode.
        shopify_site: Site model instance when the site is in Shopify mode.
        webflow_site: Site model instance when the site is in Webflow mode.
        """
        self.alias = alias
        self.knowledge_base = knowledge_base
        self.wp_site = wp_site  # if set → save via WP REST API instead of BlogPost
        self.shopify_site = shopify_site  # if set → save via Shopify Admin API
        self.webflow_site = webflow_site  # if set → save via Webflow CMS API
        self.serper_images = []
        self.logs = []

    # === KNOWLEDGE BASE ===

    def _split_kb_chunks(self):
        """Split knowledge base into chunks for targeted retrieval.
        Splits by markdown headings (##) or double newlines.
        """
        if not self.knowledge_base:
            return []
        text = self.knowledge_base.strip()
        # Prefer markdown heading splits
        if '##' in text or '#' in text.split('\n', 1)[0]:
            raw_chunks = re.split(r'\n(?=#{1,3}\s)', text)
        else:
            raw_chunks = re.split(r'\n\s*\n', text)
        return [c.strip() for c in raw_chunks if c.strip()]

    def _select_kb_chunks(self, topic_hint, max_chunks=5, max_chars=4000):
        """Pick KB chunks most relevant to topic_hint via keyword overlap.
        Returns a string, bounded by max_chars.
        """
        chunks = self._split_kb_chunks()
        if not chunks:
            return ''
        # If KB fits, return everything
        full = '\n\n'.join(chunks)
        if len(full) <= max_chars:
            return full

        # Keyword-based scoring
        hint = (topic_hint or '').lower()
        hint_words = set(re.findall(r'\w{4,}', hint))  # words ≥4 chars
        if not hint_words:
            return full[:max_chars]

        scored = []
        for chunk in chunks:
            chunk_lower = chunk.lower()
            score = sum(1 for w in hint_words if w in chunk_lower)
            if score > 0:
                scored.append((score, chunk))

        # Always keep the first chunk (often the "about me" section)
        selected = [chunks[0]] if chunks else []
        scored.sort(key=lambda x: -x[0])
        for _, chunk in scored[:max_chunks - 1]:
            if chunk not in selected:
                selected.append(chunk)

        out = '\n\n'.join(selected)
        return out[:max_chars] if len(out) > max_chars else out

    def _kb_summary(self, max_chars=500):
        """Short KB summary (first chunk / first paragraph) for prompts that
        only need author identity, not full expertise detail."""
        chunks = self._split_kb_chunks()
        if not chunks:
            return ''
        first = chunks[0]
        return first[:max_chars] + ('…' if len(first) > max_chars else '')

    def log(self, message):
        self.logs.append(message)

    # === DUPLICATE DETECTION ===

    @staticmethod
    def _title_tokens(s):
        """Normalize title to a set of meaningful tokens (lowercase, no
        accents, no stopwords, ≥3 chars). Used for cannibalization checks."""
        import re
        text = (s or '').lower()
        # strip accents
        try:
            import unicodedata
            text = ''.join(
                c for c in unicodedata.normalize('NFD', text)
                if unicodedata.category(c) != 'Mn'
            )
        except Exception:
            pass
        words = re.findall(r"[a-z0-9]+", text)
        stop = {
            'les', 'des', 'pour', 'que', 'qui', 'votre', 'vos', 'mes', 'son',
            'sur', 'dans', 'avec', 'mon', 'ses', 'cette', 'cet', 'aux', 'une',
            'tout', 'tous', 'sans', 'sous', 'plus', 'lui', 'eux', 'nos',
            'the', 'and', 'for', 'with', 'your', 'our', 'how', 'why', 'what',
            'are', 'this', 'that', 'from', 'their',
        }
        return {w for w in words if len(w) >= 3 and w not in stop}

    def _is_too_similar(self, candidate_title, existing_titles, threshold=0.55):
        """Return (matched_title, similarity) if candidate_title is too
        similar to any existing title — Jaccard on token sets."""
        a = self._title_tokens(candidate_title)
        if not a:
            return None
        best = (None, 0.0)
        for ex in existing_titles:
            b = self._title_tokens(ex)
            if not b:
                continue
            inter = len(a & b)
            union = len(a | b)
            sim = inter / union if union else 0.0
            if sim > best[1]:
                best = (ex, sim)
        if best[1] >= threshold:
            return best
        return None

    # === MAIN ENTRY POINT ===

    def generate(self, search_method='serper', topic=None, title=None,
                 article_type='news', length='medium', keywords=None, dry_run=False,
                 language='fr', brief=None):
        """
        Generate an article and optionally save it to the site's database.
        Returns dict with 'output' (text log) and 'post_count'.

        `brief` (optional dict) is the structured Content Brief produced by
        ContentBriefView. When provided, it is injected into the Claude prompt
        as a STRATEGIC BRIEF section (search intent, target word count, outline,
        FAQ, entities, schemas, EEAT signals) so the article aligns with the
        pre-writing analysis.
        """
        self.article_length = length
        self.forced_title = title
        self.article_type = article_type
        self.custom_topic = topic
        self.language = language if language in ('fr', 'en', 'es') else 'fr'
        self.seo_keywords = [k.strip() for k in keywords.split(',')] if keywords else []
        self.brief = brief if isinstance(brief, dict) else None

        config = LENGTH_CONFIG[length]

        # Validate API keys
        if not os.environ.get('ANTHROPIC_API_KEY'):
            raise ValueError('ANTHROPIC_API_KEY manquante')
        if search_method == 'serper' and not os.environ.get('SERPER_API_KEY'):
            raise ValueError('SERPER_API_KEY manquante pour la recherche Serper')
        if search_method == 'gemini' and not os.environ.get('GEMINI_API_KEY'):
            raise ValueError('GEMINI_API_KEY manquante pour la recherche Gemini')

        self.log(f'[START] Generation article ({article_type}, {length})')
        self.log(f'  Methode: {search_method}')
        if topic:
            self.log(f'  Sujet: {topic}')
        if self.seo_keywords:
            self.log(f'  Mots-cles: {", ".join(self.seo_keywords)}')

        # 1. Web search
        if topic:
            search_results = self.search_web(topic, search_method)
        else:
            search_results = self.find_auto_topic(search_method)

        # 2. Analyze and pick topic
        topic_analysis = self.analyze_and_pick_topic(search_results)
        self.log(f'[OK] Sujet: {topic_analysis["title"]}')

        # 2.5 Cannibalization guard: refuse to generate a near-duplicate of
        # an existing article (unless the user forced the title explicitly).
        if not self.forced_title:
            if self.wp_site is not None or self.shopify_site is not None or self.webflow_site is not None:
                # Fetch existing titles via the CMS adapter
                existing_titles = [a['title'] for a in self._get_existing_articles()][:60]
            else:
                existing_titles = list(
                    BlogPost.objects.using(self.alias)
                    .values_list('title', flat=True)[:60]
                )
            match = self._is_too_similar(topic_analysis['title'], existing_titles, threshold=0.55)
            if match:
                matched_title, sim = match
                self.log(f'[CANNIBAL] Trop similaire ({int(sim * 100)}%) a: "{matched_title}"')
                raise ValueError(
                    f'Cet article serait trop similaire ({int(sim * 100)}%) a un article existant: '
                    f'"{matched_title}". Reformule le sujet ou modifie l\'article existant.'
                )

        # 3. Generate article content
        content = self.generate_article_content(topic_analysis, search_results)
        self.log('[OK] Article genere')

        # 4. Replace image placeholders
        content = self.replace_image_placeholders(content, topic_analysis)

        # 5. Validate internal links
        content, broken_links = self.validate_internal_links(content)

        # 6. Validate SEO H2 keywords
        h2_valid, missing_kw = self.validate_h2_keywords(content, topic_analysis['title'])

        # 7. Cover image
        cover_image = self.get_cover_image(topic_analysis)

        # 8. Metadata
        article_title = topic_analysis['title']
        slug = slugify(article_title)
        excerpt = self.generate_excerpt(content, article_title)
        tags = self.extract_tags(content, article_title)
        reading_time = self.calculate_reading_time(content)

        self.log(f'\n[RESUME]')
        self.log(f'  Titre: {article_title}')
        self.log(f'  Slug: {slug}')
        self.log(f'  Categorie: {topic_analysis.get("category", "Actualites Tech")}')
        self.log(f'  Tags: {", ".join(tags)}')
        self.log(f'  Temps de lecture: {reading_time} min')
        if broken_links:
            self.log(f'  Liens casses corriges: {len(broken_links)}')

        # Store generated fields for inline access
        self._gen_title = article_title
        self._gen_content = f'# {article_title}\n\n{content}'
        self._gen_excerpt = excerpt
        self._gen_tags = tags
        self._gen_cover = cover_image

        if dry_run:
            self.log('\n[DRY RUN] Article non sauvegarde')
            self.log(f'\n--- META DESCRIPTION ---\n{excerpt}')
            self.log(f'\n--- CONTENU (apercu) ---\n{content[:2000]}...')
            return {
                'output': '\n'.join(self.logs),
                'post_count': 0,
            }

        # 9. Save article
        post = self.save_article(
            title=article_title,
            slug=slug,
            excerpt=excerpt,
            content=f'# {article_title}\n\n{content}',
            category_name=topic_analysis.get('category', 'Actualites IA'),
            tags=tags,
            reading_time=reading_time,
            cover_image=cover_image,
        )

        self.log(f'\n[OK] Article publie !')
        self.log(f'  Slug: {post.slug}')

        return {
            'output': '\n'.join(self.logs),
            'post_count': 1,
        }

    # === WEB SEARCH ===

    def search_web(self, query, method):
        if method == 'gemini':
            return self.search_with_gemini(query)
        return self.search_with_serper(query)

    def search_with_serper(self, query):
        self.log(f'[SEARCH] Serper: "{query}"')

        response = requests.post(
            'https://google.serper.dev/search',
            headers={
                'X-API-KEY': os.environ['SERPER_API_KEY'],
                'Content-Type': 'application/json'
            },
            json={'q': query, 'gl': 'fr', 'hl': 'fr', 'num': 10},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()

        results = ''
        if data.get('organic'):
            results += '### Resultats de recherche:\n\n'
            for item in data['organic'][:8]:
                results += f"**{item.get('title', '')}**\n"
                results += f"{item.get('snippet', '')}\n"
                results += f"Source: {item.get('link', '')}\n\n"

        if data.get('news'):
            results += '\n### Actualites recentes:\n\n'
            for item in data['news'][:5]:
                results += f"**{item.get('title', '')}** ({item.get('date', '')})\n"
                results += f"{item.get('snippet', '')}\n"
                results += f"Source: {item.get('link', '')}\n\n"

        # Image search
        try:
            img_response = requests.post(
                'https://google.serper.dev/images',
                headers={
                    'X-API-KEY': os.environ['SERPER_API_KEY'],
                    'Content-Type': 'application/json'
                },
                json={'q': query + ' AI', 'gl': 'fr', 'num': 10},
                timeout=10,
            )
            if img_response.ok:
                img_data = img_response.json()
                if img_data.get('images'):
                    self.serper_images = [
                        {
                            'url': img.get('imageUrl'),
                            'title': img.get('title', ''),
                            'source': img.get('link', '')
                        }
                        for img in img_data['images'][:10]
                        if img.get('imageUrl')
                    ]
                    self.log(f'  {len(self.serper_images)} images trouvees')
                    results += '\n### Images disponibles:\n\n'
                    for i, img in enumerate(self.serper_images[:5]):
                        results += f"{i+1}. {img['title']}\n   URL: {img['url']}\n\n"
        except Exception as e:
            self.log(f'  [WARN] Erreur images: {e}')

        self.log('[OK] Recherche terminee')
        return results

    def search_with_gemini(self, query):
        self.log(f'[SEARCH] Gemini: "{query}"')

        response = requests.post(
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent',
            params={'key': os.environ['GEMINI_API_KEY']},
            headers={'Content-Type': 'application/json'},
            json={
                'contents': [{'parts': [{'text': f'''Tu es un chercheur expert.
Recherche et analyse les informations les plus recentes sur: "{query}"

Fournis:
1. Les dernieres actualites et annonces
2. Les fonctionnalites ou changements importants
3. Les reactions de la communaute tech
4. Les implications pour les utilisateurs
5. Les sources fiables avec URLs si possible

Sois factuel et precis.'''}]}],
                'generationConfig': {'temperature': 0.3, 'maxOutputTokens': 4000}
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
        self.log('[OK] Recherche terminee')
        return text

    def find_auto_topic(self, method):
        weighted_topics = (
            PILLAR_TOPICS * 3 +
            STRATEGY_TOPICS * 3 +
            LESSONS_TOPICS * 2 +
            RESOURCES_TOPICS * 2
        )
        query = random.choice(weighted_topics)
        self.log(f'[TOPIC] Sujet auto: {query}')
        return self.search_web(query, method)

    # === CLAUDE API ===

    def call_claude(self, prompt, max_tokens=4000):
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': os.environ['ANTHROPIC_API_KEY'],
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json'
            },
            json={
                'model': 'claude-sonnet-4-20250514',
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        return data['content'][0]['text']

    # === TOPIC ANALYSIS ===

    def analyze_and_pick_topic(self, search_results):
        self.log('[ANALYSIS] Analyse des resultats...')

        # Get existing titles to avoid duplicates (from the site's DB)
        existing_titles = list(
            BlogPost.objects.using(self.alias).values_list('title', flat=True)[:30]
        )
        existing_str = '\n'.join(f'- {t}' for t in existing_titles) if existing_titles else 'Aucun article existant'

        _lang_map = {'fr': 'français', 'en': 'English', 'es': 'español'}
        _lang_native = _lang_map.get(getattr(self, 'language', 'fr'), 'français')
        language_rule = f"\n**LANGUE OBLIGATOIRE:** tous les champs JSON (title, topic, angle, keyPoints, category) doivent etre ecrits en {_lang_native}. Ne melange pas les langues.\n"

        if self.forced_title:
            self.log(f'[TITLE] Titre force: {self.forced_title}')
            prompt = f'''Tu dois structurer un article avec ce TITRE EXACT (ne le modifie PAS):
{language_rule}
TITRE IMPOSE: {self.forced_title}

Contexte de recherche:
{search_results}

Tu dois ecrire un article {self.article_type} avec EXACTEMENT ce titre.

CATEGORIES (choisis la plus adaptee):
- "Produit & Strategie" : MVP, validation idee, product-market fit
- "Croissance & Acquisition" : SEO, trafic organique, growth, monetisation
- "Lecons & Erreurs" : Apprentissages, echecs, mythes vs realite
- "Productivite & Outils" : Stack technique, automatisation, workflow

Reponds UNIQUEMENT au format JSON:
{{
  "title": "{self.forced_title}",
  "topic": "Le sujet en 2-3 mots",
  "angle": "Angle sur ce sujet",
  "keyPoints": ["point 1", "point 2", "point 3"],
  "category": "Nom exact parmi les 4 categories ci-dessus"
}}

IMPORTANT: Le champ "title" DOIT etre EXACTEMENT "{self.forced_title}".'''
            text = self.call_claude(prompt, max_tokens=1500)
            json_match = re.search(r'\{[\s\S]*\}', text)
            if not json_match:
                raise Exception('Impossible de parser la reponse de Claude')
            result = json.loads(json_match.group())
            result['title'] = self.forced_title
            return result

        if self.article_type == 'local':
            prompt = f'''Voici des resultats de recherche sur des entreprises/professionnels locaux:
{language_rule}
{search_results}

SUJET IMPOSE: {self.custom_topic or "entreprises locales"}

OBJECTIF: Creer un article ANNUAIRE/GUIDE LOCAL.

Reponds UNIQUEMENT au format JSON:
{{
  "title": "Titre incluant la ville/region",
  "topic": "{self.custom_topic or 'entreprises locales'}",
  "angle": "Guide annuaire des professionnels locaux",
  "keyPoints": ["liste des entreprises", "liens vers leurs sites", "conseils de selection"],
  "category": "Ressources Locales"
}}'''
        elif self.custom_topic:
            prompt = f'''Voici des recherches sur le sujet: "{self.custom_topic}"
{language_rule}
{search_results}

ARTICLES DEJA PUBLIES — NE PAS DUPLIQUER NI PARAPHRASER:
{existing_str}

REGLE STRICTE: Le titre que tu proposes DOIT etre fondamentalement different
de chacun de ces articles existants. Pas de simple reformulation
("L'IA pour les PME" ↔ "IA pour PME"). Si le sujet propose chevauche
un article existant, choisis un ANGLE OPPOSE OU COMPLEMENTAIRE
(ex: critique, contre-exemple, mise a jour 2026, niche specifique).

---

SUJET IMPOSE: {self.custom_topic}
Tu DOIS ecrire sur CE sujet specifique.

CATEGORIES:
- "Produit & Strategie"
- "Croissance & Acquisition"
- "Lecons & Erreurs"
- "Productivite & Outils"

Reponds UNIQUEMENT au format JSON:
{{
  "title": "Titre sur {self.custom_topic} (max 60 car)",
  "topic": "{self.custom_topic}",
  "angle": "Angle personnel sur ce sujet",
  "keyPoints": ["point 1", "point 2", "point 3"],
  "category": "Nom parmi les 4 categories ci-dessus"
}}'''
        else:
            kb_hint = ''
            kb_summary = self._kb_summary(max_chars=600)
            if kb_summary:
                kb_hint = f'''
PROFIL DE L'AUTEUR:
{kb_summary}

=> Choisis un sujet ALIGNE avec l'expertise/l'experience de l'auteur.
'''

            prompt = f'''Voici des recherches sur un sujet business/produit/entrepreneuriat:
{language_rule}
{search_results}

{kb_hint}
ARTICLES DEJA PUBLIES — NE PAS DUPLIQUER NI PARAPHRASER:
{existing_str}

REGLE STRICTE: Le titre que tu proposes DOIT etre fondamentalement different
de chacun de ces articles existants. Pas de simple reformulation
("L'IA pour les PME" ↔ "IA pour PME"). Si le sujet propose chevauche
un article existant, choisis un ANGLE OPPOSE OU COMPLEMENTAIRE
(ex: critique, contre-exemple, mise a jour 2026, niche specifique).

---

OBJECTIF: Choisir UN SUJET pour un article evergreen.

REGLES:
1. DIFFERENT des articles deja publies
2. Contenu EVERGREEN - pas de dates, pas d'actualites
3. OPINION + EXPERIENCE > tutoriel generique
4. 1 article = 1 idee forte
5. Angle PERSONNEL

CATEGORIES:
- "Produit & Strategie" : MVP, validation, product-market fit
- "Croissance & Acquisition" : SEO, trafic, growth, monetisation
- "Lecons & Erreurs" : Apprentissages, echecs, mythes vs realite
- "Productivite & Outils" : Stack technique, automatisation

FORMAT TITRE: Court et percutant (max 60 car)

Reponds UNIQUEMENT au format JSON:
{{
  "title": "Titre court et percutant (max 60 car)",
  "topic": "Sujet en 2-3 mots",
  "angle": "Angle personnel et unique",
  "keyPoints": ["point 1", "point 2", "point 3"],
  "category": "Nom exact parmi les 4 categories"
}}'''

        text = self.call_claude(prompt, max_tokens=1500)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            raise Exception('Impossible de parser la reponse de Claude')
        return json.loads(json_match.group())

    # === ARTICLE GENERATION ===

    def generate_article_content(self, topic_analysis, search_results):
        self.log('[WRITING] Generation de l\'article...')
        config = LENGTH_CONFIG[self.article_length]

        available_images = ""
        if self.serper_images:
            available_images = "\n**Images disponibles (de la recherche web):**\n"
            for i, img in enumerate(self.serper_images[:8]):
                available_images += f"- [SERPER_{i}]: {img['title']}\n"

        seo_keywords_context = ""
        if self.seo_keywords:
            seo_keywords_context = f"""
**MOTS-CLES SEO OBLIGATOIRES:**
Inclus ces mots-cles naturellement: {', '.join(self.seo_keywords)}
- Au moins 1 fois dans l'introduction
- Au moins 1 fois dans un titre H2
- 2-3 fois dans le corps du texte"""

        # Strategic content brief (from /content-brief/ if user generated one)
        brief_context = ""
        brief = getattr(self, 'brief', None) or {}
        if brief:
            outline_lines = []
            for h in brief.get('outline', [])[:15]:
                level = h.get('level', 2)
                text = (h.get('text') or '').strip()
                if text:
                    prefix = '##' if level == 2 else '###'
                    outline_lines.append(f"  {prefix} {text}")
            outline_block = '\n'.join(outline_lines) if outline_lines else '(aucun outline propose)'

            faq_lines = []
            for f in brief.get('faq', [])[:8]:
                q = (f.get('question') or '').strip()
                a = (f.get('answer_hint') or '').strip()
                if q:
                    faq_lines.append(f"  - Q: {q}\n    A (hint): {a}")
            faq_block = '\n'.join(faq_lines) if faq_lines else '(aucune FAQ)'

            entities = brief.get('entities') or []
            entities_block = ', '.join(str(e) for e in entities[:15]) if entities else '(aucune)'

            eeat = brief.get('eeat_signals') or []
            eeat_block = '\n'.join(f"  - {s}" for s in eeat[:8]) if eeat else '(aucun)'

            schemas = brief.get('schemas_suggested') or []
            schemas_block = ', '.join(str(s) for s in schemas[:8]) if schemas else '(aucun)'

            brief_context = f"""
**BRIEF STRATEGIQUE (a respecter, surtout l'outline et les entites):**

Intention de recherche: {brief.get('search_intent', 'informational')}
Longueur cible recommandee: {brief.get('word_count_target') or 'non specifiee'} mots

Plan suggere (suis cette structure pour matcher les top SERP):
{outline_block}

Entites/concepts a mentionner naturellement (pour la profondeur thematique):
{entities_block}

FAQ a inclure en fin d'article (peut etre transformee en schema FAQPage):
{faq_block}

Signaux E-E-A-T a integrer (citations, dates, references):
{eeat_block}

Schemas Schema.org pertinents pour cet article: {schemas_block}
"""

        # Get existing articles for internal linking
        existing_articles = self._get_existing_articles()
        internal_links = self._get_internal_linking_instructions(existing_articles)

        if self.article_type == 'local':
            prompt = f'''Tu ecris un article ANNUAIRE/GUIDE listant les entreprises d'une region.

**TITRE:** {topic_analysis['title']}
**REGION/SUJET:** {topic_analysis.get('topic', self.custom_topic)}

{TYPE_INSTRUCTIONS.get('local')}

**RESULTATS DE RECHERCHE:**
{search_results}

**SPECIFICATIONS:**
- Longueur: {config['words']} mots
- Sections: {config['sections']}

**REGLES:**
1. EXTRAIRE toutes les entreprises des resultats de recherche
2. Pour CHAQUE entreprise, INCLURE LE LIEN [Nom](https://url.com)
3. Ne PAS inventer d'entreprises ou d'URLs

**IMAGES:**
- [UNSPLASH: description] pour illustrations

Commence directement (pas de titre H1).'''
        else:
            # Knowledge base context — smart retrieval of relevant chunks only
            kb_context = ""
            if self.knowledge_base:
                topic_hint = ' '.join([
                    topic_analysis.get('title', ''),
                    topic_analysis.get('topic', ''),
                    topic_analysis.get('angle', ''),
                    ' '.join(topic_analysis.get('keyPoints', [])),
                ])
                kb_relevant = self._select_kb_chunks(topic_hint, max_chunks=5, max_chars=4000)
                if kb_relevant:
                    kb_context = f"""
## CONTEXTE PERSONNEL DE L'AUTEUR (extraits pertinents)
{kb_relevant}

IMPORTANT: Utilise ces informations pour ecrire avec la voix et le ton de l'auteur.
Integre naturellement ses experiences, anecdotes et opinions dans l'article.
"""
                    self.log(f'[KB] Utilise {len(kb_relevant)} chars de KB pertinents')

            lang_map = {'fr': ('français', 'French'), 'en': ('English', 'English'), 'es': ('español', 'Spanish')}
            lang_native, lang_en = lang_map.get(self.language, ('français', 'French'))

            prompt = f'''Tu es un auteur de blog professionnel.

**REGLE CRITIQUE DE LANGUE:**
Cet article doit etre ecrit ENTIEREMENT en {lang_native} ({lang_en}).
Toute la sortie (titre, intro, H2, paragraphes, conclusion) doit etre en {lang_native}.
NE MELANGE PAS les langues. NE TRADUIS PAS vers l'anglais si la cible est le francais.

{kb_context}

**SUJET:** {topic_analysis['title']}
**ANGLE:** {topic_analysis['angle']}
**POINTS CLES:** {', '.join(topic_analysis.get('keyPoints', []))}
**CATEGORIE:** {topic_analysis.get('category', 'Lecons & Erreurs')}

{TYPE_INSTRUCTIONS.get(self.article_type, TYPE_INSTRUCTIONS['guide'])}

{seo_keywords_context}

{brief_context}

**RECHERCHES (pour contexte):**
{search_results}

---

**SPECIFICATIONS:**
- Longueur: {config['words']} mots
- Sections: {config['sections']}
- Images: {config['images']}

**TON & STYLE:**
1. PREMIERE PERSONNE - "J'ai", "Mon", "Je pense que"
2. OPINIONS TRANCHEES - pas de "ca depend"
3. EXEMPLES PERSONNELS
4. DIRECT ET PRAGMATIQUE
5. VULNERABLE - admets tes erreurs
6. ZERO BULLSHIT

**STRUCTURE SEO:**
- Introduction accrocheuse
- ## Titres H2 clairs (2-4 mots)
- Paragraphes courts (3-4 phrases max)
- **Gras** pour les idees cles
- Listes a puces
- Conclusion avec 1 action concrete

{internal_links}

**IMAGES ({config['images']}):**
- [UNSPLASH: description en anglais] pour illustrations
{available_images}

**IMPORTANT:**
- Ecris TOUT l'article ({config['words']} mots minimum)
- Commence directement (pas de titre H1)
- Termine par une conclusion memorable
- Contenu EVERGREEN
- INCLUS 2-3 liens internes vers les articles existants'''

        return self.call_claude(prompt, max_tokens=config['tokens'])

    # === IMAGE HANDLING ===

    def get_ai_logo(self, tool_name):
        tool_lower = tool_name.lower().strip()
        for key, url in AI_LOGOS.items():
            if key in tool_lower or tool_lower in key:
                return url
        return None

    def get_unsplash_image(self, query):
        access_key = os.environ.get('UNSPLASH_ACCESS_KEY')
        if not access_key:
            return None
        try:
            response = requests.get(
                'https://api.unsplash.com/photos/random',
                params={'query': query, 'orientation': 'landscape'},
                headers={'Authorization': f'Client-ID {access_key}'},
                timeout=10,
            )
            if response.ok:
                data = response.json()
                return data['urls']['regular']
        except Exception:
            pass
        return None

    def get_pollinations_image(self, prompt):
        from urllib.parse import quote
        enhanced_prompt = f"{prompt}, professional tech blog cover, modern minimalist design, high quality"
        encoded = quote(enhanced_prompt)
        return f"https://image.pollinations.ai/prompt/{encoded}?width=1600&height=900&nologo=true"

    def is_valid_image_url(self, url):
        if not url:
            return False
        blocked_domains = [
            'linkedin.com', 'licdn.com', 'facebook.com', 'fbcdn.net',
            'twitter.com', 'twimg.com', 'instagram.com', 'placehold.co',
        ]
        url_lower = url.lower()
        for domain in blocked_domains:
            if domain in url_lower:
                return False
        if not url.startswith('http'):
            return False
        return True

    def get_cover_image(self, topic_analysis):
        topic = topic_analysis.get('topic', 'technology')
        title = topic_analysis.get('title', topic)
        self.log('[COVER] Recherche image de couverture...')

        # Check for AI logo
        main_tool = topic_analysis.get('main_ai_tool', '').lower()
        if main_tool:
            logo = self.get_ai_logo(main_tool)
            if logo:
                return logo

        # Try Unsplash
        img = self.get_unsplash_image(f'{topic} technology startup')
        if img:
            return img

        # Fallback: Pollinations
        self.log('  Fallback: Pollinations')
        return self.get_pollinations_image(f'{topic} technology programming developer')

    def replace_image_placeholders(self, content, topic_analysis):
        self.log('[IMG] Traitement des images...')

        # 1. Logos [LOGO: name]
        for match in re.finditer(r'\[LOGO:\s*([^\]]+)\]', content):
            tool_name = match.group(1)
            logo_url = self.get_ai_logo(tool_name)
            if logo_url:
                content = content.replace(match.group(0), f'\n\n![Logo {tool_name}]({logo_url})\n\n')
            else:
                url = self.get_unsplash_image(f'{tool_name} AI') or ''
                if url:
                    content = content.replace(match.group(0), f'\n\n![{tool_name}]({url})\n\n')
                else:
                    content = content.replace(match.group(0), '')

        # 2. Serper images [SERPER_0], [SERPER_1], etc.
        for match in re.finditer(r'\[SERPER_(\d+)\]', content):
            idx = int(match.group(1))
            if idx < len(self.serper_images):
                img = self.serper_images[idx]
                img_url = img.get('url', '')
                if self.is_valid_image_url(img_url):
                    content = content.replace(match.group(0), f'\n\n![{img["title"]}]({img_url})\n\n')
                else:
                    fallback_url = self.get_unsplash_image(img.get('title', 'technology'))
                    if fallback_url:
                        content = content.replace(match.group(0), f'\n\n![{img["title"]}]({fallback_url})\n\n')
                    else:
                        content = content.replace(match.group(0), '')
            else:
                content = content.replace(match.group(0), '')

        # 3. Unsplash [UNSPLASH: description]
        for match in re.finditer(r'\[UNSPLASH:\s*([^\]]+)\]', content):
            desc = match.group(1)
            url = self.get_unsplash_image(desc)
            if url:
                content = content.replace(match.group(0), f'\n\n![{desc}]({url})\n\n')
            else:
                content = content.replace(match.group(0), '')

        # 4. Direct URLs [URL: https://...]
        for match in re.finditer(r'\[URL:\s*([^\]]+)\]', content):
            url = match.group(1).strip()
            content = content.replace(match.group(0), f'\n\n![Image]({url})\n\n')

        # 5. Legacy [IMAGE: description]
        for match in re.finditer(r'\[IMAGE:\s*([^\]]+)\]', content):
            desc = match.group(1)
            url = self.get_unsplash_image(desc)
            if url:
                content = content.replace(match.group(0), f'\n\n![{desc}]({url})\n\n')
            else:
                content = content.replace(match.group(0), '')

        return content

    # === VALIDATION ===

    def validate_internal_links(self, content):
        self.log('[LINKS] Validation des liens internes...')
        internal_link_pattern = r'\[([^\]]+)\]\(/blog/([^)]+)\)'
        matches = re.findall(internal_link_pattern, content)

        if not matches:
            return content, []

        if self.wp_site is not None or self.shopify_site is not None or self.webflow_site is not None:
            existing_slugs = {a['slug'] for a in self._get_existing_articles()}
        else:
            existing_slugs = set(
                BlogPost.objects.using(self.alias).values_list('slug', flat=True)
            )

        broken_links = []
        for link_text, slug in matches:
            if slug not in existing_slugs:
                broken_links.append((link_text, slug))

        if broken_links:
            for link_text, slug in broken_links:
                broken_pattern = f'\\[{re.escape(link_text)}\\]\\(/blog/{re.escape(slug)}\\)'
                content = re.sub(broken_pattern, link_text, content)
            self.log(f'  {len(broken_links)} lien(s) casse(s) corriges')

        return content, broken_links

    def validate_h2_keywords(self, content, title):
        if not self.seo_keywords:
            return True, []

        h2_titles = re.findall(r'^##\s+(.+)$', content, re.MULTILINE)
        if not h2_titles:
            return True, []

        h2_text = ' '.join(h2_titles).lower()
        missing = [kw for kw in self.seo_keywords if kw.lower() not in h2_text]
        return len(missing) == 0, missing

    # === METADATA ===

    def generate_excerpt(self, content, title):
        self.log('[META] Generation meta description...')
        keywords_str = ', '.join(self.seo_keywords[:3]) if self.seo_keywords else ''

        prompt = f'''Genere une meta description SEO pour cet article de blog.

TITRE: {title}
DEBUT DU CONTENU: {content[:1000]}
{f"MOTS-CLES: {keywords_str}" if keywords_str else ""}

REGLES:
1. Entre 150 et 160 caracteres EXACTEMENT
2. Commence par un verbe d'action ou une question
3. Inclut le sujet principal
4. Donne envie de cliquer
5. Pas de guillemets, pas d'emojis

Reponds UNIQUEMENT avec la meta description.'''

        try:
            meta = self.call_claude(prompt, max_tokens=100)
            meta = meta.strip().strip('"').strip("'")
            if len(meta) > 160:
                meta = meta[:157] + '...'
            elif len(meta) < 120:
                raise Exception('Meta trop courte')
            return meta
        except Exception:
            return self._extract_fallback_excerpt(content, title)

    def _extract_fallback_excerpt(self, content, title):
        clean = content
        clean = re.sub(r'^#+\s+.+$', '', clean, flags=re.MULTILINE)
        clean = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', clean)
        clean = re.sub(r'\[[^\]]*\]\([^)]+\)', '', clean)
        clean = re.sub(r'https?://[^\s\)]+', '', clean)
        clean = re.sub(r'\*\*', '', clean)
        clean = re.sub(r'\*', '', clean)
        clean = re.sub(r'`[^`]+`', '', clean)
        clean = re.sub(r'\n+', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        sentences = [s.strip() for s in re.split(r'[.!?]+', clean)
                     if len(s.strip()) > 20 and 'http' not in s]

        if sentences:
            excerpt = sentences[0][:157]
            return excerpt + ('...' if len(excerpt) >= 157 else '.')

        return f'Decouvrez notre guide complet sur {title}.'[:160]

    def extract_tags(self, content, title):
        text = (content + ' ' + title).lower()
        tags = []

        keywords = {
            'mvp': 'MVP', 'saas': 'SaaS', 'startup': 'Startup',
            'validation': 'Validation', 'pivot': 'Pivot',
            'seo': 'SEO', 'trafic': 'Trafic', 'croissance': 'Croissance',
            'monetisation': 'Monetisation', 'conversion': 'Conversion',
            'erreur': 'Erreurs', 'echec': 'Echecs', 'lecon': 'Lecons',
            'productivite': 'Productivite', 'automatisation': 'Automatisation',
            'side project': 'Side Project', 'solo founder': 'Solo Founder',
            'django': 'Django', 'react': 'React', 'python': 'Python',
            'javascript': 'JavaScript', 'api': 'API', 'no-code': 'No-Code',
            'intelligence artificielle': 'IA', ' ia ': 'IA', ' ai ': 'IA',
        }

        for kw, tag in keywords.items():
            if kw in text and tag not in tags:
                tags.append(tag)

        if not tags:
            tags.append('Entrepreneuriat')

        return tags[:6]

    def calculate_reading_time(self, content):
        words = len(content.split())
        return max(1, words // 200)

    # === INTERNAL LINKING HELPERS ===

    def _get_existing_articles(self):
        # WordPress mode: fetch via REST API (capped at 50 to keep prompt size sane).
        if self.wp_site is not None:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                client = WordPressClient(self.wp_site)
                page = client.list_posts(status='published', per_page=50)
                return [
                    {
                        'title': p.get('title') or '',
                        'slug': p.get('slug') or '',
                        'url': f"/{p.get('slug') or ''}",
                        'excerpt': (p.get('excerpt') or '')[:100],
                        'category': '',
                    }
                    for p in page.get('results', [])
                ]
            except WordPressError:
                return []

        # Shopify mode: fetch via Admin API (capped at 50).
        if self.shopify_site is not None:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                client = ShopifyClient(self.shopify_site)
                page = client.list_posts(status='published', per_page=50)
                return [
                    {
                        'title': p.get('title') or '',
                        'slug': p.get('slug') or '',
                        'url': f"/blogs/{client.blog_id or 'news'}/{p.get('slug') or ''}",
                        'excerpt': (p.get('excerpt') or '')[:100],
                        'category': '',
                    }
                    for p in page.get('results', [])
                ]
            except ShopifyError:
                return []

        # Webflow mode: fetch via CMS API (capped at 50).
        if self.webflow_site is not None:
            from .webflow_adapter import WebflowClient, WebflowError
            try:
                client = WebflowClient(self.webflow_site)
                page = client.list_posts(status='published', per_page=50)
                return [
                    {
                        'title': p.get('title') or '',
                        'slug': p.get('slug') or '',
                        'url': f"/blog/{p.get('slug') or ''}",
                        'excerpt': (p.get('excerpt') or '')[:100],
                        'category': '',
                    }
                    for p in page.get('results', [])
                ]
            except WebflowError:
                return []

        articles = (
            BlogPost.objects.using(self.alias)
            .all()
            .values('title', 'slug', 'excerpt', 'category__name')
        )
        return [
            {
                'title': a['title'],
                'slug': a['slug'],
                'url': f"/blog/{a['slug']}",
                'excerpt': (a['excerpt'] or '')[:100],
                'category': a['category__name'],
            }
            for a in articles
        ]

    def _get_internal_linking_instructions(self, existing_articles):
        if not existing_articles:
            return ""

        articles_list = '\n'.join(
            f"- [{a['title']}]({a['url']})" for a in existing_articles[:10]
        )

        return f"""
## MAILLAGE INTERNE

Inclus au minimum 2 liens internes vers des articles existants dans le contenu.
Integre-les naturellement dans le texte, pas dans une section separee.

Articles disponibles:
{articles_list}

Exemples: "D'ailleurs, j'ai ecrit un article complet sur [ce sujet](/blog/slug)..."
"""

    # === SAVE ===

    def save_article(self, title, slug, excerpt, content, category_name, tags, reading_time, cover_image):
        # WordPress mode: push to WP REST API instead of saving locally.
        if self.wp_site is not None:
            from .wordpress_adapter import WordPressClient, WordPressError
            try:
                client = WordPressClient(self.wp_site)
                # Convert markdown content to HTML for WP (WP renders raw HTML; markdown isn't natively supported).
                from markdown import markdown as md_to_html
                content_html = md_to_html(
                    content, extensions=['extra', 'tables', 'fenced_code']
                )
                created = client.create_post(
                    title=title,
                    content=content_html,
                    excerpt=excerpt,
                    slug=slug,
                    status='publish',
                )
                self.log(f'[OK] Article publie sur WordPress (id={created.get("wp_id")})')
                # Return a duck-typed object with .slug/.title attributes (used by callers).

                class _WpPostShim:
                    pass
                shim = _WpPostShim()
                shim.slug = created.get('slug') or slug
                shim.title = created.get('title') or title
                shim.id = created.get('wp_id')
                return shim
            except WordPressError as e:
                self.log(f'[ERROR] WP save failed: {e}')
                raise

        # Webflow mode: push to CMS API (live publish).
        if self.webflow_site is not None:
            from .webflow_adapter import WebflowClient, WebflowError
            try:
                client = WebflowClient(self.webflow_site)
                from markdown import markdown as md_to_html
                content_html = md_to_html(
                    content, extensions=['extra', 'tables', 'fenced_code']
                )
                created = client.create_post(
                    title=title,
                    content=content_html,
                    excerpt=excerpt,
                    slug=slug,
                    status='published',
                    featured_image_url=cover_image or '',
                )
                self.log(f'[OK] Article publie sur Webflow (id={created.get("webflow_id")})')

                class _WebflowPostShim:
                    pass
                shim = _WebflowPostShim()
                shim.slug = created.get('slug') or slug
                shim.title = created.get('title') or title
                shim.id = created.get('webflow_id')
                return shim
            except WebflowError as e:
                self.log(f'[ERROR] Webflow save failed: {e}')
                raise

        # Shopify mode: push to Admin API.
        if self.shopify_site is not None:
            from .shopify_adapter import ShopifyClient, ShopifyError
            try:
                client = ShopifyClient(self.shopify_site)
                from markdown import markdown as md_to_html
                content_html = md_to_html(
                    content, extensions=['extra', 'tables', 'fenced_code']
                )
                created = client.create_post(
                    title=title,
                    content=content_html,
                    excerpt=excerpt,
                    slug=slug,
                    status='published',
                    author=self.shopify_site.author_for_articles,
                    tags=tags,
                    featured_image_url=cover_image or '',
                )
                self.log(f'[OK] Article publie sur Shopify (id={created.get("shopify_id")})')

                class _ShopifyPostShim:
                    pass
                shim = _ShopifyPostShim()
                shim.slug = created.get('slug') or slug
                shim.title = created.get('title') or title
                shim.id = created.get('shopify_id')
                return shim
            except ShopifyError as e:
                self.log(f'[ERROR] Shopify save failed: {e}')
                raise

        # Check for duplicate slug
        if BlogPost.objects.using(self.alias).filter(slug=slug).exists():
            slug = f"{slug}-{date.today().strftime('%Y%m%d')}"

        # Add "A lire aussi" section
        content = self._add_related_articles_section(content, category_name, tags, slug)

        # Get or create category
        category, _ = Category.objects.using(self.alias).get_or_create(
            slug=slugify(category_name),
            defaults={'name': category_name}
        )

        # Create article — respect target language
        post = BlogPost(
            title=title,
            slug=slug,
            excerpt=excerpt,
            content=content,
            author='Admin',
            category=category,
            cover_image=cover_image or '',
            reading_time=reading_time,
            featured=False,
            published_at=date.today(),
            language=getattr(self, 'language', 'fr'),
        )
        post.save(using=self.alias)

        # Add tags
        for tag_name in tags:
            tag, _ = Tag.objects.using(self.alias).get_or_create(name=tag_name)
            post.tags.add(tag)

        self.log('[OK] Article sauvegarde')
        return post

    def _add_related_articles_section(self, content, category_name, tags, current_slug):
        related = self._get_related_articles(category_name, tags, current_slug)
        if not related:
            return content

        section = "\n\n---\n\n## A lire aussi\n\n"
        for post in related:
            section += f"- [{post.title}](/blog/{post.slug})\n"

        return content + section

    def _get_related_articles(self, category_name, tags, exclude_slug, limit=3):
        # CMS modes (WP, Shopify, Webflow): skip the "A lire aussi" auto-section
        # since we'd need remote API category/tag matching, overkill for MVP.
        if self.wp_site is not None or self.shopify_site is not None or self.webflow_site is not None:
            return []

        related = []

        try:
            category = (
                Category.objects.using(self.alias)
                .filter(name__icontains=category_name.split('&')[0].strip())
                .first()
            )
            if category:
                category_posts = (
                    BlogPost.objects.using(self.alias)
                    .filter(category=category)
                    .exclude(slug=exclude_slug)
                    .order_by('-published_at')[:limit]
                )
                related.extend(list(category_posts))
        except Exception:
            pass

        if len(related) < limit:
            for tag_name in tags[:3]:
                tag_posts = (
                    BlogPost.objects.using(self.alias)
                    .filter(tags__name__iexact=tag_name)
                    .exclude(slug=exclude_slug)
                    .order_by('-published_at')[:limit - len(related)]
                )
                for post in tag_posts:
                    if post not in related:
                        related.append(post)
                        if len(related) >= limit:
                            break

        if len(related) < limit:
            recent = (
                BlogPost.objects.using(self.alias)
                .exclude(slug=exclude_slug)
                .order_by('-published_at')[:limit - len(related)]
            )
            for post in recent:
                if post not in related:
                    related.append(post)

        return related[:limit]
