"""Prompt export - turn a HostedLanding or StrategicOpportunity into a
ready-to-paste prompt for the user's AI coding assistant.

Why this exists: clients who build their site with an AI tool (ChatGPT,
Lovable, v0, Bolt, Copilot...) but have no CMS can't receive pages via the
WordPress / Shopify / Webflow adapters, and they don't run an MCP-connected
agent either. The deliverable for them is a PROMPT - their own AI does the
integration in their own codebase. Gridar never touches their repo.

Two modes, two sources:

  - HostedLanding -> "INTEGRATE" prompt. The copy already exists and was
    calibrated on the target keyword: the user's AI must NOT rewrite it,
    only integrate it (meta, structure, JSON-LD, exact slug).

  - StrategicOpportunity -> "CREATE" prompt. Only the strategic concept
    exists (hook, capture mechanism, conversion path, angle): the user's
    AI writes the copy following the brief.

Pure templating - no LLM call, no quota, instant. The instruction language
follows the content language (fr -> French scaffolding, else English).
"""
from __future__ import annotations

import json

from django.utils.text import slugify

# Stacks we know how to give specific integration instructions for.
# 'generic' is the fallback and must always exist in both languages.
SUPPORTED_STACKS = (
    'nextjs', 'react', 'html', 'astro', 'wordpress', 'webflow', 'generic',
)


def normalize_stack(value: str | None) -> str:
    v = (value or '').strip().lower()
    return v if v in SUPPORTED_STACKS else 'generic'


def _txt(value) -> str:
    """Coerce any JSON value to a stripped string ('' for None).

    Landing / opportunity JSON fields come from unvalidated API payloads -
    a question or a title can legally be an int or a nested object
    (V1CreateLandingView persists faq/value_props without per-item
    validation). Every place that renders user JSON goes through here so a
    weird value degrades to its str() form instead of a 500.
    """
    if value is None:
        return ''
    return str(value).strip()


def _valid_faq(faq) -> list[dict]:
    """Keep only dict entries that actually carry a question."""
    if not isinstance(faq, list):
        return []
    return [q for q in faq if isinstance(q, dict) and _txt(q.get('question'))]


def _valid_props(value_props) -> list[dict]:
    """Keep only dict entries that actually carry a title."""
    if not isinstance(value_props, list):
        return []
    return [
        v for v in value_props
        if isinstance(v, dict) and _txt(v.get('title'))
    ]


# Obviously-templated placeholders. A missing Site.domain must NEVER ship a
# plausible-looking fake domain ('ton-domaine.com' resolves for someone
# else) into a canonical URL the client's AI injects verbatim.
_DOMAIN_PLACEHOLDER_FR = 'TON-DOMAINE.example'
_DOMAIN_PLACEHOLDER_EN = 'YOUR-DOMAIN.example'


def _site_domain(site, lang: str) -> tuple[str, bool]:
    """Return (domain, is_real)."""
    domain = (site.domain or '').strip().rstrip('/')
    if domain:
        return domain, True
    placeholder = _DOMAIN_PLACEHOLDER_FR if lang == 'fr' else _DOMAIN_PLACEHOLDER_EN
    return placeholder, False


# ---------------------------------------------------------------------------
# Stack-specific instruction blocks.
# Plain strings with a literal "{slug}" placeholder substituted via .replace()
# (NOT str.format - the JS snippets contain braces that would break it).
# ---------------------------------------------------------------------------

_STACK_FR = {
    'nextjs': (
        "Next.js (App Router) : cree `app/{slug}/page.tsx`. Exporte `metadata` "
        "(title, description, alternates.canonical, openGraph). Injecte chaque "
        "bloc JSON-LD via `<script type=\"application/ld+json\" "
        "dangerouslySetInnerHTML={{ __html: JSON.stringify(donnees) }} />`. "
        "Si le projet utilise encore le Pages Router : `pages/{slug}.tsx` avec "
        "`next/head`."
    ),
    'react': (
        "React SPA : ajoute la route `/{slug}` dans ton router. Au montage du "
        "composant, mets a jour `document.title`, la meta description et le "
        "lien canonical (react-helmet, ou un useEffect qui ecrit dans "
        "document.head). Injecte les JSON-LD en creant des elements "
        "`<script type=\"application/ld+json\">` dans le head au montage et "
        "retire-les au demontage."
    ),
    'html': (
        "HTML statique : cree le fichier `{slug}/index.html` (ou `{slug}.html` "
        "selon ta config serveur) avec tout dans un seul fichier. Reprends la "
        "feuille de style existante du site pour rester coherent visuellement."
    ),
    'astro': (
        "Astro : cree `src/pages/{slug}.astro`. Les meta vont dans le frontmatter "
        "ou ton composant Layout habituel. Injecte les JSON-LD dans le <head> "
        "via `<script type=\"application/ld+json\" set:html={JSON.stringify(donnees)} />`."
    ),
    'wordpress': (
        "WordPress : cree une nouvelle page avec le slug EXACT `{slug}`. Colle "
        "le contenu dans l'editeur (Gutenberg : utilise des blocs titres/"
        "paragraphes/accordeon). Le title et la meta description se configurent "
        "via ton plugin SEO (Yoast ou RankMath). Les JSON-LD : ajoute un bloc "
        "HTML personnalise contenant les deux balises <script>."
    ),
    'webflow': (
        "Webflow : cree une page statique au slug EXACT `{slug}`. Reproduis les "
        "sections avec les elements Webflow (Hero, Grid pour les cartes, "
        "Accordion pour la FAQ). Title + meta description dans Page Settings. "
        "Les deux JSON-LD vont dans Page Settings > Custom Code > Inside <head>."
    ),
    'generic': (
        "Utilise les conventions de ton framework. Les invariants a respecter "
        "peu importe le stack : le slug exact, l'ordre des sections, les meta "
        "dans le <head>, et les deux blocs JSON-LD injectes tels quels."
    ),
}

_STACK_EN = {
    'nextjs': (
        "Next.js (App Router): create `app/{slug}/page.tsx`. Export `metadata` "
        "(title, description, alternates.canonical, openGraph). Inject each "
        "JSON-LD block via `<script type=\"application/ld+json\" "
        "dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }} />`. "
        "On the Pages Router: `pages/{slug}.tsx` with `next/head`."
    ),
    'react': (
        "React SPA: add the `/{slug}` route to your router. On mount, update "
        "`document.title`, the meta description and the canonical link "
        "(react-helmet or a useEffect writing into document.head). Inject the "
        "JSON-LD blocks as `<script type=\"application/ld+json\">` elements "
        "on mount, remove them on unmount."
    ),
    'html': (
        "Static HTML: create `{slug}/index.html` (or `{slug}.html` depending on "
        "your server config) as a single self-contained file. Reuse the site's "
        "existing stylesheet to stay visually consistent."
    ),
    'astro': (
        "Astro: create `src/pages/{slug}.astro`. Meta goes in the frontmatter "
        "or your usual Layout component. Inject JSON-LD in <head> via "
        "`<script type=\"application/ld+json\" set:html={JSON.stringify(data)} />`."
    ),
    'wordpress': (
        "WordPress: create a new page with the EXACT slug `{slug}`. Paste the "
        "content into the editor (Gutenberg: headings/paragraphs/accordion "
        "blocks). Title + meta description via your SEO plugin (Yoast or "
        "RankMath). JSON-LD: add a custom HTML block with both <script> tags."
    ),
    'webflow': (
        "Webflow: create a static page with the EXACT slug `{slug}`. Rebuild "
        "the sections with Webflow elements (Hero, Grid for cards, Accordion "
        "for the FAQ). Title + meta description in Page Settings. Both JSON-LD "
        "blocks go in Page Settings > Custom Code > Inside <head>."
    ),
    'generic': (
        "Use your framework's conventions. The invariants regardless of stack: "
        "the exact slug, the section order, the meta tags in <head>, and both "
        "JSON-LD blocks injected verbatim."
    ),
}


def _stack_block(stack: str, slug: str, lang: str) -> str:
    table = _STACK_FR if lang == 'fr' else _STACK_EN
    return table[normalize_stack(stack)].replace('{slug}', slug or 'page')


# ---------------------------------------------------------------------------
# JSON-LD builders (mirror the frontend LandingRenderer logic so the prompt
# carries the same schema a hosted render would emit).
# ---------------------------------------------------------------------------

def _primary_jsonld(landing, canonical_url: str) -> dict:
    explicit = landing.schema_jsonld or {}
    if isinstance(explicit, dict) and '@type' in explicit:
        return explicit
    lang_tag = {'fr': 'fr-CA', 'es': 'es'}.get(landing.language, 'en-CA')
    base = {
        '@context': 'https://schema.org',
        '@type': landing.schema_type or 'WebPage',
        'name': landing.h1 or landing.title,
        'headline': landing.title,
        'description': landing.meta_description or landing.hero_subtitle,
        'url': canonical_url,
        'inLanguage': lang_tag,
    }
    if landing.cover_image:
        base['image'] = landing.cover_image
    return base


def _faq_jsonld(faq: list) -> dict | None:
    entries = [
        {
            '@type': 'Question',
            'name': _txt(q.get('question')),
            'acceptedAnswer': {
                '@type': 'Answer',
                'text': _txt(q.get('answer')),
            },
        }
        for q in _valid_faq(faq)
    ]
    if not entries:
        # No valid Q/A -> no FAQPage at all. An empty mainEntity is invalid
        # schema.org markup, and the prompt orders verbatim injection.
        return None
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': entries,
    }


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# INTEGRATE mode - HostedLanding -> prompt
# ---------------------------------------------------------------------------

def build_landing_prompt(landing, site, stack: str = 'generic') -> str:
    lang = (landing.language or 'fr')[:2]
    fr = lang == 'fr'
    domain, domain_is_real = _site_domain(site, lang)
    slug = landing.slug or 'page'
    canonical = f'https://{domain}/{slug}'

    value_props = _valid_props(landing.value_props)
    faq = _valid_faq(landing.faq)
    primary_ld = _primary_jsonld(landing, canonical)
    faq_ld = _faq_jsonld(faq)

    domain_note_fr = (
        "\n- ATTENTION : le domaine n'est pas configure dans Gridar. "
        f"Remplace `{domain}` par le vrai domaine du site PARTOUT "
        "(canonical, og:url, JSON-LD) avant de publier."
    )
    domain_note_en = (
        "\n- WARNING: the domain is not configured in Gridar. Replace "
        f"`{domain}` with the site's real domain EVERYWHERE (canonical, "
        "og:url, JSON-LD) before publishing."
    )

    sections: list[str] = []

    if fr:
        sections.append(
            f"# Mission : integrer une page SEO sur {domain}\n\n"
            "Tu es developpeur. Tu vas integrer une page d'atterrissage SEO "
            f"deja redigee sur le site {domain}. La copy a ete calibree pour "
            f"ranker sur le mot-cle \"{landing.target_keyword or slug}\" : tu "
            "ne dois PAS la reecrire, la resumer ni l'ameliorer. Ton travail "
            "= structure, integration et style. Pas le texte."
        )
        sections.append(
            "## Regles absolues\n"
            "1. Le texte fourni est le texte final. Recopie-le tel quel "
            "(accents, guillemets et gras compris).\n"
            f"2. URL de la page : exactement `/{slug}` (pas de variante, pas "
            "de prefixe de dossier, pas de date).\n"
            "3. Une seule balise <h1> sur la page : celle fournie plus bas.\n"
            "4. Les blocs JSON-LD fournis a la fin doivent etre injectes TELS "
            "QUELS dans le <head>.\n"
            "5. Adapte les couleurs et la typo au design system existant du "
            "site. Ne change pas l'ordre des sections."
        )
        sections.append(
            "## Meta SEO (head)\n"
            f"- `<title>` : {landing.title}\n"
            f"- `<meta name=\"description\">` : {landing.meta_description or landing.hero_subtitle}\n"
            f"- `<link rel=\"canonical\" href=\"{canonical}\">`\n"
            "- Open Graph : og:title = le title, og:description = la "
            "description, og:url = le canonical, og:type = website\n"
            f"- Langue declaree de la page : {lang}"
            + ('' if domain_is_real else domain_note_fr)
        )
        hero = (
            "## Structure de la page (dans cet ordre)\n\n"
            "### 1. Hero\n"
            f"- H1 : {landing.h1}\n"
        )
        if landing.hero_subtitle:
            hero += f"- Sous-titre : {landing.hero_subtitle}\n"
        if landing.hero_cta_text and landing.hero_cta_url:
            hero += (
                f"- Bouton CTA principal : \"{landing.hero_cta_text}\" "
                f"-> lien vers `{landing.hero_cta_url}`"
            )
        sections.append(hero.rstrip())

        if value_props:
            cards = [
                f"### 2. Grille de benefices ({len(value_props)} cartes)"
            ]
            for vp in value_props:
                cards.append(
                    f"- [icone suggeree : {_txt(vp.get('icon')) or 'aucune'}] "
                    f"**{_txt(vp.get('title'))}** : {_txt(vp.get('description'))}"
                )
            sections.append('\n'.join(cards))

        if landing.body_markdown and landing.body_markdown.strip():
            sections.append(
                "### 3. Contenu principal\n"
                "Rends ce markdown en HTML (h2/h3, listes, tableaux, code "
                "inline). Ne reformule rien :\n\n"
                "---DEBUT CONTENU---\n"
                f"{landing.body_markdown.strip()}\n"
                "---FIN CONTENU---"
            )

        if faq:
            items = [
                "### 4. FAQ (accordeon - questions fermees par defaut, "
                "cliquables, navigables au clavier)"
            ]
            for q in faq:
                items.append(
                    f"**Q : {_txt(q.get('question'))}**\n"
                    f"R : {_txt(q.get('answer'))}"
                )
            sections.append('\n\n'.join(items))

        if landing.cta_bottom_text and landing.cta_bottom_url:
            sections.append(
                "### 5. CTA final\n"
                "- Un court titre d'appel a l'action (libre)\n"
                f"- Bouton : \"{landing.cta_bottom_text}\" -> "
                f"`{landing.cta_bottom_url}`"
            )

        ld = (
            "## JSON-LD (copier tel quel dans le <head>)\n\n"
            "Bloc 1 :\n"
            "```json\n" + _dumps(primary_ld) + "\n```"
        )
        if faq_ld:
            ld += "\n\nBloc 2 (FAQ) :\n```json\n" + _dumps(faq_ld) + "\n```"
        sections.append(ld)

        sections.append(
            "## Specifique a ton stack\n" + _stack_block(stack, slug, lang)
        )
        sections.append(
            "## Checklist avant de terminer\n"
            f"- [ ] Le slug de la page est exactement `/{slug}`\n"
            "- [ ] Il y a un seul h1\n"
            "- [ ] Les scripts application/ld+json sont presents dans le head\n"
            "- [ ] Le texte n'a pas ete reformule\n"
            "- [ ] La page est responsive (mobile d'abord)\n"
            "- [ ] La FAQ est utilisable au clavier"
        )
    else:
        sections.append(
            f"# Mission: integrate an SEO page on {domain}\n\n"
            "You are a developer. You will integrate an already-written SEO "
            f"landing page on {domain}. The copy was calibrated to rank on "
            f"the keyword \"{landing.target_keyword or slug}\": do NOT "
            "rewrite, summarize or 'improve' it. Your job is structure, "
            "integration and styling. Not the words."
        )
        sections.append(
            "## Hard rules\n"
            "1. The provided text is final. Reproduce it verbatim.\n"
            f"2. Page URL: exactly `/{slug}` (no variant, no folder prefix, "
            "no date).\n"
            "3. Exactly one <h1> on the page: the one provided below.\n"
            "4. The JSON-LD blocks at the end must be injected VERBATIM in "
            "<head>.\n"
            "5. Match the site's existing design system for colors and type. "
            "Do not reorder sections."
        )
        sections.append(
            "## SEO meta (head)\n"
            f"- `<title>`: {landing.title}\n"
            f"- `<meta name=\"description\">`: {landing.meta_description or landing.hero_subtitle}\n"
            f"- `<link rel=\"canonical\" href=\"{canonical}\">`\n"
            "- Open Graph: og:title = title, og:description = description, "
            "og:url = canonical, og:type = website\n"
            f"- Declared page language: {lang}"
            + ('' if domain_is_real else domain_note_en)
        )
        hero = (
            "## Page structure (in this order)\n\n"
            "### 1. Hero\n"
            f"- H1: {landing.h1}\n"
        )
        if landing.hero_subtitle:
            hero += f"- Subtitle: {landing.hero_subtitle}\n"
        if landing.hero_cta_text and landing.hero_cta_url:
            hero += (
                f"- Primary CTA button: \"{landing.hero_cta_text}\" "
                f"-> link to `{landing.hero_cta_url}`"
            )
        sections.append(hero.rstrip())

        if value_props:
            cards = [f"### 2. Benefits grid ({len(value_props)} cards)"]
            for vp in value_props:
                cards.append(
                    f"- [suggested icon: {_txt(vp.get('icon')) or 'none'}] "
                    f"**{_txt(vp.get('title'))}**: {_txt(vp.get('description'))}"
                )
            sections.append('\n'.join(cards))

        if landing.body_markdown and landing.body_markdown.strip():
            sections.append(
                "### 3. Main content\n"
                "Render this markdown as HTML (h2/h3, lists, tables, inline "
                "code). Do not rephrase anything:\n\n"
                "---CONTENT START---\n"
                f"{landing.body_markdown.strip()}\n"
                "---CONTENT END---"
            )

        if faq:
            items = [
                "### 4. FAQ (accordion - collapsed by default, clickable, "
                "keyboard accessible)"
            ]
            for q in faq:
                items.append(
                    f"**Q: {_txt(q.get('question'))}**\n"
                    f"A: {_txt(q.get('answer'))}"
                )
            sections.append('\n\n'.join(items))

        if landing.cta_bottom_text and landing.cta_bottom_url:
            sections.append(
                "### 5. Final CTA\n"
                "- A short call-to-action heading (your choice)\n"
                f"- Button: \"{landing.cta_bottom_text}\" -> "
                f"`{landing.cta_bottom_url}`"
            )

        ld = (
            "## JSON-LD (copy verbatim into <head>)\n\n"
            "Block 1:\n```json\n" + _dumps(primary_ld) + "\n```"
        )
        if faq_ld:
            ld += "\n\nBlock 2 (FAQ):\n```json\n" + _dumps(faq_ld) + "\n```"
        sections.append(ld)

        sections.append(
            "## Stack-specific instructions\n" + _stack_block(stack, slug, lang)
        )
        sections.append(
            "## Final checklist\n"
            f"- [ ] Page slug is exactly `/{slug}`\n"
            "- [ ] Exactly one h1\n"
            "- [ ] application/ld+json scripts present in head\n"
            "- [ ] Copy was not rephrased\n"
            "- [ ] Page is responsive (mobile first)\n"
            "- [ ] FAQ is keyboard accessible"
        )

    return '\n\n'.join(sections)


# ---------------------------------------------------------------------------
# CREATE mode - StrategicOpportunity -> prompt
# ---------------------------------------------------------------------------

def build_opportunity_prompt(opportunity, site, stack: str = 'generic') -> str:
    lang = (opportunity.language or 'fr')[:2]
    fr = lang == 'fr'
    domain, domain_is_real = _site_domain(site, lang)
    concept = opportunity.concept if isinstance(opportunity.concept, dict) else {}

    suggested = concept.get('suggested_url_path')
    suggested = suggested.strip() if isinstance(suggested, str) else ''
    if suggested:
        url_path = suggested if suggested.startswith('/') else '/' + suggested
    else:
        # slugify strips accents / apostrophes / uppercase so a FR-CA
        # keyword like "referencement web Quebec" never becomes a
        # non-ASCII mixed-case URL the prompt then mandates as exact.
        url_path = '/' + (slugify(opportunity.keyword) or 'page')
    slug = url_path.lstrip('/')
    canonical = f'https://{domain}{url_path}'

    domain_note_fr = (
        "\n- ATTENTION : le domaine n'est pas configure dans Gridar. "
        f"Remplace `{domain}` par le vrai domaine du site PARTOUT "
        "(canonical, og:url, JSON-LD) avant de publier."
    )
    domain_note_en = (
        "\n- WARNING: the domain is not configured in Gridar. Replace "
        f"`{domain}` with the site's real domain EVERYWHERE (canonical, "
        "og:url, JSON-LD) before publishing."
    )

    schema_type = {
        'comparison': 'Product',
        'local_landing': 'LocalBusiness',
    }.get(concept.get('page_type') or '', 'Service')

    sections: list[str] = []

    if fr:
        sections.append(
            f"# Mission : creer une page SEO qui convertit sur {domain}\n\n"
            "Tu es a la fois developpeur et copywriter. Tu vas CREER une page "
            f"complete pour le site {site.name or domain} en suivant ce brief "
            "strategique. Ici tu rediges la copy toi-meme, mais le brief est "
            "contraignant : chaque element marque (a respecter) doit se "
            "retrouver dans la page."
        )
        site_block = (
            "## Le site\n"
            f"- Nom : {site.name or '(sans nom)'}\n"
            f"- Domaine : {domain}\n"
            f"- Modele d'affaires : {site.business_model or 'inconnu'}\n"
        )
        if (site.description or '').strip():
            site_block += f"- Description : {site.description.strip()}\n"
        if site.primary_cta_text:
            site_block += (
                f"- CTA produit existant : \"{site.primary_cta_text}\""
                + (f" -> {site.primary_cta_url}" if site.primary_cta_url else "")
            )
        sections.append(site_block.rstrip())

        kw_block = (
            "## Le mot-cle cible\n"
            f"- \"{opportunity.keyword}\" (intent : {opportunity.intent})\n"
            f"- Langue de redaction : {lang}"
        )
        if fr:
            kw_block += (
                "\n- IMPORTANT : redige en francais QUEBECOIS. Ecris "
                "\"magasinage\" (pas \"shopping\"), \"fin de semaine\" (pas "
                "\"week-end\"), \"courriel\" (pas \"mail\"). Le lectorat est "
                "au Quebec."
            )
        sections.append(kw_block)

        concept_block = ["## Le brief strategique (a respecter)"]
        mapping = [
            ('page_type', 'Type de page'),
            ('suggested_title', 'Titre suggere'),
            ('hook', 'Hook (l\'accroche qui fait cliquer)'),
            ('capture_mechanism', 'Mecanisme de capture du lead'),
            ('conversion_path', 'Chemin de conversion'),
            ('angle', 'Angle face aux concurrents du SERP'),
            ('asset_used', 'Asset du site a exploiter'),
            ('why_this_works', 'Pourquoi ca marche'),
        ]
        for key, label in mapping:
            value = concept.get(key)
            if value:
                concept_block.append(f"- {label} : {value}")
        concept_block.append(f"- URL de la page : `{url_path}`")
        sections.append('\n'.join(concept_block))

        sections.append(
            "## Structure attendue\n"
            "1. **Hero** : un H1 qui contient le mot-cle, un sous-titre qui "
            "materialise le hook, un bouton CTA.\n"
            "2. **3 a 5 benefices** en cartes (titre court + 1-2 phrases).\n"
            "3. **600 a 1200 mots de contenu** qui developpent l'angle. "
            "Hierarchie h2/h3 propre, le mot-cle present dans au moins 2 h2.\n"
            "4. **FAQ** : 4 a 6 questions que se posent vraiment les gens qui "
            f"cherchent \"{opportunity.keyword}\", avec des reponses "
            "completes (2-4 phrases).\n"
            "5. **CTA final** aligne sur le chemin de conversion decrit dans "
            "le brief."
        )
        sections.append(
            "## Meta SEO\n"
            f"- `<title>` : moins de 60 caracteres, contient \"{opportunity.keyword}\"\n"
            "- `<meta name=\"description\">` : 140 a 160 caracteres\n"
            f"- `<link rel=\"canonical\" href=\"{canonical}\">`\n"
            f"- JSON-LD : un bloc `{schema_type}` (nom, description, url) + un "
            "bloc `FAQPage` construit sur tes questions/reponses. Les deux "
            "dans des balises `<script type=\"application/ld+json\">`."
            + ('' if domain_is_real else domain_note_fr)
        )
        sections.append(
            "## Specifique a ton stack\n" + _stack_block(stack, slug, lang)
        )
        sections.append(
            "## Checklist avant de terminer\n"
            f"- [ ] L'URL est exactement `{url_path}`\n"
            "- [ ] Un seul h1, et il contient le mot-cle\n"
            "- [ ] Le hook du brief est visible dans le hero\n"
            "- [ ] Le mecanisme de capture est implemente (pas juste mentionne)\n"
            "- [ ] JSON-LD " + schema_type + " + FAQPage presents dans le head\n"
            "- [ ] Lexique quebecois respecte (zero \"week-end\", zero \"shopping\")"
        )
    else:
        sections.append(
            f"# Mission: create an SEO page that converts on {domain}\n\n"
            "You are both a developer and a copywriter. You will CREATE a "
            f"complete page for {site.name or domain} following this "
            "strategic brief. You write the copy yourself, but the brief is "
            "binding: every element marked (required) must appear on the page."
        )
        site_block = (
            "## The site\n"
            f"- Name: {site.name or '(unnamed)'}\n"
            f"- Domain: {domain}\n"
            f"- Business model: {site.business_model or 'unknown'}\n"
        )
        if (site.description or '').strip():
            site_block += f"- Description: {site.description.strip()}\n"
        if site.primary_cta_text:
            site_block += (
                f"- Existing product CTA: \"{site.primary_cta_text}\""
                + (f" -> {site.primary_cta_url}" if site.primary_cta_url else "")
            )
        sections.append(site_block.rstrip())

        sections.append(
            "## Target keyword\n"
            f"- \"{opportunity.keyword}\" (intent: {opportunity.intent})\n"
            f"- Writing language: {lang}"
        )

        concept_block = ["## Strategic brief (required)"]
        mapping = [
            ('page_type', 'Page type'),
            ('suggested_title', 'Suggested title'),
            ('hook', 'Hook (what earns the click)'),
            ('capture_mechanism', 'Lead capture mechanism'),
            ('conversion_path', 'Conversion path'),
            ('angle', 'Angle vs current SERP competitors'),
            ('asset_used', 'Site asset to leverage'),
            ('why_this_works', 'Why this works'),
        ]
        for key, label in mapping:
            value = concept.get(key)
            if value:
                concept_block.append(f"- {label}: {value}")
        concept_block.append(f"- Page URL: `{url_path}`")
        sections.append('\n'.join(concept_block))

        sections.append(
            "## Expected structure\n"
            "1. **Hero**: an H1 containing the keyword, a subtitle that "
            "delivers the hook, a CTA button.\n"
            "2. **3 to 5 benefits** as cards (short title + 1-2 sentences).\n"
            "3. **600 to 1200 words of content** developing the angle. Clean "
            "h2/h3 hierarchy, keyword present in at least 2 h2s.\n"
            "4. **FAQ**: 4 to 6 questions real searchers of "
            f"\"{opportunity.keyword}\" actually ask, with complete answers "
            "(2-4 sentences).\n"
            "5. **Final CTA** aligned with the conversion path from the brief."
        )
        sections.append(
            "## SEO meta\n"
            f"- `<title>`: under 60 characters, contains \"{opportunity.keyword}\"\n"
            "- `<meta name=\"description\">`: 140 to 160 characters\n"
            f"- `<link rel=\"canonical\" href=\"{canonical}\">`\n"
            f"- JSON-LD: one `{schema_type}` block (name, description, url) + "
            "one `FAQPage` block built from your Q&As. Both inside "
            "`<script type=\"application/ld+json\">` tags."
            + ('' if domain_is_real else domain_note_en)
        )
        sections.append(
            "## Stack-specific instructions\n" + _stack_block(stack, slug, lang)
        )
        sections.append(
            "## Final checklist\n"
            f"- [ ] URL is exactly `{url_path}`\n"
            "- [ ] Exactly one h1, containing the keyword\n"
            "- [ ] The brief's hook is visible in the hero\n"
            "- [ ] The capture mechanism is implemented (not just mentioned)\n"
            "- [ ] JSON-LD " + schema_type + " + FAQPage present in head"
        )

    return '\n\n'.join(sections)
