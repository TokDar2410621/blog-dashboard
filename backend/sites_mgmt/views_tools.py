"""Public lead-magnet tool endpoints (no auth required).

Separated from the main views.py (11k+ lines) for maintainability.
All views follow the same pattern as PublicAuditView:
- authentication_classes = []  (no session CSRF enforcement)
- permission_classes = []      (public)
- throttle_classes for abuse prevention
- domain cache (1h) to avoid re-spending API budget
- partial free results + gated full report behind email capture
"""
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle as _AnonRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class PublicToolThrottle(_AnonRateThrottle):
    """3 analyses per IP per minute for public tool endpoints."""
    rate = '3/min'


def _normalize_domain(raw: str):
    """Reuse the same normalizer as the public audit."""
    if not raw:
        return None
    raw = raw.strip().lower()
    raw = raw.replace('https://', '').replace('http://', '')
    raw = raw.rstrip('/').split('/')[0]
    raw = raw.replace('www.', '', 1) if raw.startswith('www.') else raw
    if '.' not in raw or ' ' in raw:
        return None
    return raw


def _get_client_ip(request):
    """Extract client IP, respecting X-Forwarded-For."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _crawl_homepage_light(url: str) -> dict:
    """Quick homepage fetch: title, meta description, h1."""
    import requests as http_requests
    try:
        r = http_requests.get(url, timeout=10, headers={
            'User-Agent': 'Gridar-Bot/1.0 (+https://gridar.app)',
        }, allow_redirects=True)
        if r.status_code != 200:
            return {'error': f'HTTP {r.status_code}'}
        html = r.text[:50000]
        import re
        # react-wrap-balancer (et des libs similaires) injectent un <script>
        # a l'interieur meme du <h1> pour equilibrer les lignes du titre.
        # Sans ce retrait, son code JavaScript se retrouvait dans le H1 lu,
        # puis dans un prompt envoye a Gemini par l'outil Can I Rank. Meme
        # correctif que le crawl de l'audit public.
        html_texte = re.sub(r'<script[^>]*>.*?</script>', ' ', html,
                            flags=re.I | re.DOTALL)
        html_texte = re.sub(r'<style[^>]*>.*?</style>', ' ', html_texte,
                            flags=re.I | re.DOTALL)
        title_m = re.search(r'<title[^>]*>([^<]+)</title>', html_texte, re.I)
        title = title_m.group(1).strip() if title_m else ''
        # `[^<]+` exigeait un H1 sans une seule balise a l'interieur, ce qui
        # rate tout hero moderne (un <span> pour colorer un mot, un <br> pour
        # la coupure de ligne).
        h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', html_texte, re.I | re.DOTALL)
        h1 = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', h1_m.group(1))).strip() if h1_m else ''
        desc_m = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\'\s]',
            html, re.I,
        )
        desc = desc_m.group(1).strip() if desc_m else ''
        # Le HTML complet n'est plus rendu : _detect_brand_and_sector ne le
        # lisait que pour un scan de sous-chaine sur toute la page, retire
        # ci-dessous au profit de ces trois champs cibles. Voir leur commentaire.
        return {'title': title, 'h1': h1, 'meta_description': desc}
    except Exception as e:
        return {'error': str(e)[:100]}


# Secteurs reconnus par la detection marque/secteur, LLM et heuristique de
# repli confondus. Partages pour que les deux methodes parlent le meme
# vocabulaire en aval (generation de requetes, affichage).
_SECTEURS_CONNUS = (
    'dental', 'legal', 'plumbing', 'restaurant', 'real_estate', 'accounting',
    'saas', 'ecommerce', 'marketing', 'agency', 'seo', 'health', 'general',
)

_SYSTEME_SECTEUR = (
    "Tu es analyste marketing. On te donne le titre, le H1 et la description "
    "de la page d'accueil d'une entreprise. Tu rends UNIQUEMENT un objet JSON "
    "avec sa marque et son secteur d'activite reel, rien d'autre autour."
)

_GABARIT_SECTEUR = """\
Domaine : {domain}
Titre : {title}
H1 : {h1}
Meta description : {description}

Rends un objet JSON, exactement cette forme :
{{"brand": "...", "sector": "..."}}

Regles :
- "brand" est le nom de l'entreprise elle-meme (1 a 3 mots), pas un slogan.
- "sector" doit decrire ce que l'entreprise VEND reellement, choisi parmi :
  {secteurs}. Si rien ne correspond precisement, rends "general".
- Ignore tout exemple, cas d'usage ou nom cite en demonstration sur la page :
  le secteur decrit l'entreprise elle-meme, pas ce dont sa page parle en
  passant.
"""


def _detecter_marque_secteur_llm(crawl: dict, domain: str, timeout: int = 10) -> dict | None:
    """DeepSeek lit title/H1/description et identifie marque + secteur.

    Rend None des que le resultat n'est pas exploitable ; jamais de
    dependance dure a un LLM sur ces routes publiques, l'appelant reprend
    l'heuristique de repli.

    Contrairement a un scan de sous-chaine, le modele distingue "cette
    entreprise vend X" de "cette page mentionne X en exemple". C'est
    precisement ce qui manquait le 2026-08-24 : la page d'accueil de Gridar
    cite "restaurant a Montreal" comme cas d'usage dans un mockup, et affiche
    le domaine fictif "boutique-demo.ca" dans un autre. Un scan de la page
    entiere lisait "boutique" et concluait a tort que Gridar vend en ligne.
    """
    import re

    from .llm import call_deepseek

    if not crawl or crawl.get('error'):
        return None
    title = (crawl.get('title') or '').strip()
    h1 = (crawl.get('h1') or '').strip()
    desc = (crawl.get('meta_description') or '').strip()
    if not (title or h1 or desc):
        return None

    prompt = _GABARIT_SECTEUR.format(
        domain=domain, title=title[:200], h1=h1[:200], description=desc[:300],
        secteurs=', '.join(_SECTEURS_CONNUS),
    )
    try:
        brut = call_deepseek(prompt, max_tokens=150, system=_SYSTEME_SECTEUR,
                             timeout=timeout)
    except Exception:  # noqa: BLE001 - call_deepseek avale deja tout, ceinture
        logger.exception('detection marque/secteur par LLM indisponible')
        return None
    if not brut:
        return None

    bloc = re.search(r'\{.*?\}', brut, re.DOTALL)
    if not bloc:
        return None
    try:
        data = json.loads(bloc.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None

    brand = ' '.join(str(data.get('brand') or '').split()).strip()
    sector = str(data.get('sector') or '').strip().lower()
    if not (2 <= len(brand) <= 60):
        return None
    if sector not in _SECTEURS_CONNUS:
        return None
    return {'brand': brand, 'sector': sector, 'source': 'llm'}


def _detect_brand_and_sector(crawl: dict, domain: str) -> dict:
    """Heuristique de repli : marque et secteur devines par sous-chaine, sur
    le titre, le H1 et la meta description SEULEMENT.

    Restreint le 2026-08-24 : la version precedente scannait tout le HTML de
    la page (jusqu'a 50 Ko), donc n'importe quel contenu decoratif pouvait
    detourner la classification entiere. La page d'accueil de Gridar affiche
    le domaine fictif d'un dashboard de demonstration, "boutique-demo.ca" :
    le scanner lisait "boutique" n'importe ou sur la page et concluait que
    Gridar est un site e-commerce, ce qui polluait ensuite les requetes
    generees pour le propre auto-audit de visibilite IA de Gridar.

    Se limiter aux trois champs qui decrivent reellement l'entreprise reduit
    beaucoup la marge d'erreur, meme si ca reste un test de sous-chaine : le
    chemin LLM ci-dessus est la methode fiable, celle-ci n'est que son repli.
    """
    title = crawl.get('title', '')
    # Brand = first segment before | or - in the title
    brand = title.split('|')[0].split(' - ')[0].strip() if title else domain.split('.')[0].capitalize()
    texte = ' '.join([
        crawl.get('title', ''), crawl.get('h1', ''), crawl.get('meta_description', ''),
    ]).lower()
    sector_hints = {
        'dentiste': 'dental', 'dentaire': 'dental', 'dental': 'dental',
        'avocat': 'legal', 'lawyer': 'legal', 'juridique': 'legal',
        'plombier': 'plumbing', 'plomberie': 'plumbing',
        'restaurant': 'restaurant', 'cuisine': 'restaurant',
        'immobilier': 'real_estate', 'courtier': 'real_estate', 'realtor': 'real_estate',
        'comptable': 'accounting', 'comptabilite': 'accounting',
        'saas': 'saas', 'software': 'saas', 'logiciel': 'saas',
        'ecommerce': 'ecommerce', 'boutique': 'ecommerce', 'shop': 'ecommerce',
        'marketing': 'marketing', 'agence': 'agency',
        'seo': 'seo', 'referencement': 'seo',
        'sante': 'health', 'clinique': 'health', 'medecin': 'health',
    }
    sector = 'general'
    for hint, cat in sector_hints.items():
        if hint in texte:
            sector = cat
            break
    return {'brand': brand, 'sector': sector, 'source': 'heuristique'}


def _marque_et_secteur(crawl: dict, domain: str) -> dict:
    """Point d'entree unique des 3 outils publics qui en ont besoin : DeepSeek
    d'abord, repli heuristique sinon. Jamais de dependance dure a un LLM."""
    return _detecter_marque_secteur_llm(crawl, domain) or _detect_brand_and_sector(crawl, domain)


def _generate_commercial_queries(brand: str, sector: str, domain: str, n: int = 15) -> list[str]:
    """Generate commercial queries for AI visibility testing.

    Uses Gemini if available, otherwise falls back to template queries.
    """
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if gemini_key:
        try:
            import requests as http_requests
            prompt = (
                f"Generate {n} commercial search queries (in French Canadian) "
                f"that a potential customer would type to find a business like '{brand}' "
                f"in the '{sector}' sector. "
                f"Do NOT include the brand name '{brand}' in the queries. "
                f"Focus on service discovery, comparisons, and local intent. "
                f"Return ONLY a JSON array of strings, no explanations."
            )
            r = http_requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}',
                json={'contents': [{'parts': [{'text': prompt}]}]},
                timeout=15,
            )
            if r.status_code == 200:
                text = r.json()['candidates'][0]['content']['parts'][0]['text']
                # Strip markdown code fences if present
                text = text.strip()
                if text.startswith('```'):
                    text = text.split('\n', 1)[1] if '\n' in text else text[3:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
                if text.startswith('json'):
                    text = text[4:].strip()
                queries = json.loads(text)
                if isinstance(queries, list) and len(queries) >= 5:
                    return queries[:n]
        except Exception:
            logger.exception('Gemini query generation failed, using fallback')

    # Fallback templates
    templates = [
        'meilleur {sector} Montreal',
        '{sector} recommande Quebec',
        'comparatif {sector} 2026',
        'quel {sector} choisir',
        '{sector} prix abordable',
        'avis {sector} Montreal',
        '{sector} fiable Quebec',
        'top {sector} Canada',
        '{sector} professionnel pres de chez moi',
        '{sector} urgence Montreal',
        'comment choisir un bon {sector}',
        '{sector} en ligne Quebec',
        'alternative a {sector} populaire',
        'nouveau {sector} 2026',
        '{sector} pour entreprise',
    ]
    return [t.format(sector=sector) for t in templates[:n]]


_SYSTEME_REQUETES_COMMERCIALES = (
    "Tu es analyste marketing. On te donne le titre, le H1 et la description "
    "de la page d'accueil d'une entreprise. Tu rends UNIQUEMENT un tableau "
    "JSON de requetes commerciales, rien d'autre autour."
)

_GABARIT_REQUETES_COMMERCIALES = """\
Entreprise : {brand} ({domain})
Titre : {title}
H1 : {h1}
Meta description : {description}

Rends entre 5 et {maximum} requetes, en francais quebecois, qu'un CLIENT
potentiel taperait pour trouver une entreprise comme celle-ci, en JSON, dans
cette forme exacte : ["requete un", "requete deux"]

Regles :
- Ecris ce qu'un client cherche, pas ce que l'entreprise dit d'elle-meme.
- N'inclus PAS le nom de la marque "{brand}" dans les requetes, sauf si
  c'est litteralement ce qu'on chercherait.
- Deux a six mots par requete : decouverte de service, comparaisons, intention
  locale.
- Si la page ne dit pas assez clairement ce que vend l'entreprise, rends un
  tableau vide plutot que d'inventer.
"""


def _requetes_commerciales_llm(crawl: dict, brand: str, domain: str,
                               n: int = 15, timeout: int = 15) -> list[str] | None:
    """DeepSeek lit title/H1/description et genere directement les requetes
    commerciales qu'un client taperait, sans passer par une case de secteur.

    Rend None des que le resultat n'est pas exploitable ; l'appelant retombe
    sur `_generate_commercial_queries`, qui route par secteur.

    Pourquoi : `_SECTEURS_CONNUS` ne couvre que 13 verticales locales
    (dentiste, avocat, plombier...). Un developpeur web freelance, ou
    n'importe quelle entreprise hors de ces cases, tombe sur le secteur
    'general' - et l'ancien generateur de repli substituait ce mot
    LITTERALEMENT dans ses gabarits ("meilleur general Montreal", "comparatif
    general 2026"), montre tel quel a un visiteur. Constate le 2026-08-24 sur
    tokamdarius.ca. En lisant directement le contenu reel de la page, ce
    chemin n'a plus besoin d'une case de secteur du tout.
    """
    import re

    from .llm import call_deepseek

    if not crawl or crawl.get('error'):
        return None
    title = (crawl.get('title') or '').strip()
    h1 = (crawl.get('h1') or '').strip()
    desc = (crawl.get('meta_description') or '').strip()
    if not (title or h1 or desc):
        return None

    prompt = _GABARIT_REQUETES_COMMERCIALES.format(
        brand=brand or domain, domain=domain, title=title[:200], h1=h1[:200],
        description=desc[:300], maximum=n,
    )
    try:
        brut = call_deepseek(prompt, max_tokens=400,
                             system=_SYSTEME_REQUETES_COMMERCIALES, timeout=timeout)
    except Exception:  # noqa: BLE001 - call_deepseek avale deja tout, ceinture
        logger.exception('requetes commerciales par LLM indisponibles')
        return None
    if not brut:
        return None

    bloc = re.search(r'\[.*?\]', brut, re.DOTALL)
    if not bloc:
        return None
    try:
        brut_liste = json.loads(bloc.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(brut_liste, list):
        return None

    propres: list[str] = []
    vus: set[str] = set()
    for item in brut_liste:
        if not isinstance(item, str):
            continue
        requete = ' '.join(item.split()).strip(' "\'.,;:!?')
        if not (3 <= len(requete) <= 80):
            continue
        if not (2 <= len(requete.split()) <= 6):
            continue
        if re.search(r'https?://|www\.|[<>{}]', requete):
            continue
        cle = requete.lower()
        if cle in vus:
            continue
        vus.add(cle)
        propres.append(requete)
        if len(propres) >= n:
            break

    return propres if len(propres) >= 3 else None


def _check_ai_mention(query: str, domain: str, engine: str) -> dict:
    """Check if a domain is mentioned in an AI engine's response to a query.

    Currently uses Gemini (free tier). Architecture supports adding more engines.
    Returns dict with: engine, query, mentioned, position, competitors, excerpt.
    """
    result = {
        'engine': engine,
        'query': query,
        'mentioned': False,
        'position': None,
        'competitors': [],
        'excerpt': '',
        'source_urls': [],
    }

    gemini_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_key:
        result['error'] = 'API key not configured'
        return result

    if engine == 'gemini':
        try:
            import requests as http_requests
            r = http_requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}',
                json={
                    'contents': [{'parts': [{'text': query}]}],
                    'generationConfig': {'maxOutputTokens': 500},
                },
                timeout=20,
            )
            if r.status_code == 200:
                text = r.json()['candidates'][0]['content']['parts'][0]['text']
                result['excerpt'] = text[:500]
                dom_bare = domain.replace('www.', '')
                text_lower = text.lower()
                result['mentioned'] = dom_bare in text_lower

                # Detect competitor mentions (common domains in the text)
                import re
                urls_found = re.findall(r'[a-z0-9][-a-z0-9]*\.[a-z]{2,}', text_lower)
                competitors = []
                for u in urls_found:
                    if u != dom_bare and u not in ('e.g', 'i.e', 'etc.'):
                        if u not in competitors:
                            competitors.append(u)
                result['competitors'] = competitors[:10]

                if result['mentioned']:
                    idx = text_lower.index(dom_bare)
                    result['position'] = text_lower[:idx].count('.') + 1
        except Exception as e:
            result['error'] = str(e)[:100]

    return result


def _compute_visibility_score(results: list[dict]) -> dict:
    """Compute AI Visibility Score from a list of AI check results.

    Formula:
      visibilityScore =
        mentionRate * 0.40
      + averagePositionScore * 0.25
      + citationRate * 0.20
      + shareOfVoice * 0.15

    Returns dict with score and breakdown.
    """
    total = len(results)
    if total == 0:
        return {'score': 0, 'mention_rate': 0, 'citation_rate': 0,
                'share_of_voice': 0, 'position_score': 0}

    mentions = sum(1 for r in results if r.get('mentioned'))
    mention_rate = (mentions / total) * 100

    # Position score: higher is better. Position 1 = 100, 2 = 80, etc.
    position_scores = []
    for r in results:
        if r.get('mentioned') and r.get('position'):
            pos = r['position']
            position_scores.append(max(0, 100 - (pos - 1) * 20))
    avg_position_score = sum(position_scores) / len(position_scores) if position_scores else 0

    # Citation rate: how often the domain appears with a URL
    citations = sum(1 for r in results if r.get('mentioned') and r.get('source_urls'))
    citation_rate = (citations / total) * 100 if total else 0

    # Share of voice vs competitors
    all_competitors = []
    for r in results:
        all_competitors.extend(r.get('competitors', []))
    total_mentions_all = mentions + len(all_competitors)
    share_of_voice = (mentions / total_mentions_all * 100) if total_mentions_all > 0 else 0

    score = round(
        mention_rate * 0.40
        + avg_position_score * 0.25
        + citation_rate * 0.20
        + share_of_voice * 0.15
    )
    score = max(0, min(100, score))

    return {
        'score': score,
        'mention_rate': round(mention_rate, 1),
        'citation_rate': round(citation_rate, 1),
        'share_of_voice': round(share_of_voice, 1),
        'position_score': round(avg_position_score, 1),
    }


class PublicAiVisibilityView(APIView):
    """POST /api/public/ai-visibility/ {domain}

    Public lead-magnet: checks if a domain is mentioned by AI engines
    when users ask commercial questions relevant to that domain's sector.

    Returns partial results immediately (score + 3 queries + top competitors).
    Full report (all queries, all competitors, recommendations) gated behind email.
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PublicToolThrottle]

    def post(self, request):
        domain = _normalize_domain(request.data.get('domain', ''))
        if not domain:
            return Response(
                {'error': 'Domaine invalide. Ex: monsite.com'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f'public-ai-visibility:v1:{domain}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # Step 1: crawl homepage for brand/sector detection
        homepage = f'https://{domain}'
        crawl = _crawl_homepage_light(homepage)
        meta = _marque_et_secteur(crawl, domain)
        brand = meta['brand']
        sector = meta['sector']
        sector_source = meta['source']

        # Step 2: generate commercial queries. DeepSeek d'abord, en lisant la
        # page reelle : ne depend d'aucune case de secteur, donc marche aussi
        # pour une entreprise hors des 13 verticales connues. Repli sur le
        # generateur par secteur seulement si le LLM echoue.
        queries = _requetes_commerciales_llm(crawl, brand, domain, n=15)
        queries_source = 'llm'
        if not queries:
            queries = _generate_commercial_queries(brand, sector, domain, n=15)
            queries_source = 'sector_fallback'

        # Step 3: check AI mentions (parallel, Gemini only for now)
        ai_results = []
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(_check_ai_mention, q, domain, 'gemini'): q
                for q in queries
            }
            for fut in as_completed(futures):
                try:
                    ai_results.append(fut.result())
                except Exception:
                    pass

        # Step 4: compute scores
        scores = _compute_visibility_score(ai_results)

        # Step 5: identify top competitors
        from collections import Counter
        all_comps = []
        for r in ai_results:
            all_comps.extend(r.get('competitors', []))
        top_competitors = [{'domain': d, 'mentions': c}
                          for d, c in Counter(all_comps).most_common(10)]

        # Step 6: find queries where competitors appear but not the domain
        competitor_only_queries = [
            {'query': r['query'], 'competitors': r['competitors'][:3]}
            for r in ai_results
            if not r.get('mentioned') and r.get('competitors')
        ]

        # Build payload
        # Free: score + 3 sample queries + 3 competitors + engine breakdown
        # Gated: full query list, all competitors, recommendations
        mentioned_queries = [r for r in ai_results if r.get('mentioned')]
        sample_queries = [
            {'query': r['query'], 'engine': r['engine'], 'mentioned': r['mentioned']}
            for r in ai_results[:3]
        ]

        # Per-engine breakdown (for now just Gemini, architecture ready for more)
        engine_breakdown = {}
        for r in ai_results:
            eng = r['engine']
            if eng not in engine_breakdown:
                engine_breakdown[eng] = {'total': 0, 'mentioned': 0}
            engine_breakdown[eng]['total'] += 1
            if r.get('mentioned'):
                engine_breakdown[eng]['mentioned'] += 1
        for eng in engine_breakdown:
            t = engine_breakdown[eng]['total']
            m = engine_breakdown[eng]['mentioned']
            engine_breakdown[eng]['rate'] = round(m / t * 100) if t else 0

        payload = {
            'domain': domain,
            'brand': brand,
            'sector': sector,
            'sector_source': sector_source,
            'queries_source': queries_source,
            'analyzed_at': datetime.utcnow().isoformat(),
            'ai_visibility_score': scores['score'],
            'scores_breakdown': scores,
            'engine_breakdown': engine_breakdown,
            'total_queries_tested': len(ai_results),
            'total_mentions': sum(1 for r in ai_results if r.get('mentioned')),
            'top_competitors': top_competitors[:3],  # Free: 3
            'sample_queries': sample_queries,  # Free: 3
            # Gated data
            'gated': {
                'all_competitors': top_competitors,
                'competitor_only_queries': competitor_only_queries,
                'all_results': [
                    {
                        'query': r['query'],
                        'engine': r['engine'],
                        'mentioned': r.get('mentioned', False),
                        'position': r.get('position'),
                        'competitors': r.get('competitors', [])[:5],
                        'excerpt': r.get('excerpt', '')[:200],
                    }
                    for r in ai_results
                ],
                'competitor_only_count': len(competitor_only_queries),
            },
        }

        # Save to ToolAnalysis
        from .models import ToolAnalysis
        ToolAnalysis.objects.create(
            domain=domain,
            tool='ai_visibility',
            status='completed',
            score=scores['score'],
            result=payload,
            ip=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )

        cache.set(cache_key, payload, timeout=3600)
        return Response(payload)


class PublicCompetitorGapView(APIView):
    """POST /api/public/competitor-gap/ {domain, competitors?}

    Public lead-magnet: finds keywords that competitors rank for but the
    target domain does not. Uses Serper to compare SERP visibility.

    Returns top 5 opportunities free, full report gated behind email.
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PublicToolThrottle]

    def post(self, request):
        import requests as http_requests

        domain = _normalize_domain(request.data.get('domain', ''))
        if not domain:
            return Response(
                {'error': 'Domaine invalide. Ex: monsite.com'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        cache_key = f'public-competitor-gap:v1:{domain}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        # User-provided competitors (optional)
        raw_competitors = request.data.get('competitors', [])
        if isinstance(raw_competitors, str):
            raw_competitors = [c.strip() for c in raw_competitors.split(',') if c.strip()]
        provided_competitors = [_normalize_domain(c) for c in raw_competitors if _normalize_domain(c)]

        serper_key = os.environ.get('SERPER_API_KEY')
        if not serper_key:
            return Response(
                {'error': 'Service temporairement indisponible.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Step 1: discover competitors if not provided
        competitors = provided_competitors[:3]
        if not competitors:
            try:
                r = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                    json={'q': f'site:{domain}', 'num': 10, 'hl': 'fr', 'gl': 'ca'},
                    timeout=10,
                )
                if r.status_code == 200:
                    organic = r.json().get('organic', [])
                    # Extract related searches for competitor discovery
                    related = r.json().get('relatedSearches', [])
                    related_queries = [rs.get('query', '') for rs in related[:3]]

                    # Search for a related query to find competitors
                    if related_queries:
                        for rq in related_queries[:2]:
                            cr = http_requests.post(
                                'https://google.serper.dev/search',
                                headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                                json={'q': rq, 'num': 10, 'hl': 'fr', 'gl': 'ca'},
                                timeout=8,
                            )
                            if cr.status_code == 200:
                                for item in cr.json().get('organic', []):
                                    link = (item.get('link') or '').lower()
                                    host = link.split('://', 1)[-1].split('/', 1)[0]
                                    if host.startswith('www.'):
                                        host = host[4:]
                                    if host and host != domain and host not in competitors:
                                        competitors.append(host)
                                        if len(competitors) >= 3:
                                            break
                            if len(competitors) >= 3:
                                break
            except Exception:
                logger.exception('Competitor discovery failed')

        if not competitors:
            competitors = []  # Will still work but with limited gap data

        # Step 2: crawl homepage for brand/sector
        crawl = _crawl_homepage_light(f'https://{domain}')
        meta = _marque_et_secteur(crawl, domain)

        # Step 3: get keywords that competitors rank for
        competitor_keywords = {}  # keyword -> {competitor, position, url, title}
        domain_keywords = set()   # keywords where the domain appears

        def _serp_check(query: str) -> tuple:
            """Return (query, organic_results_list)."""
            try:
                r = http_requests.post(
                    'https://google.serper.dev/search',
                    headers={'X-API-KEY': serper_key, 'Content-Type': 'application/json'},
                    json={'q': query, 'num': 20, 'hl': 'fr', 'gl': 'ca'},
                    timeout=8,
                )
                if r.status_code == 200:
                    return (query, r.json().get('organic', []))
            except Exception:
                pass
            return (query, [])

        # Generate test queries. DeepSeek d'abord, en lisant la page reelle ;
        # repli sur le generateur par secteur seulement si le LLM echoue.
        test_queries = _requetes_commerciales_llm(crawl, meta['brand'], domain, n=20)
        if not test_queries:
            test_queries = _generate_commercial_queries(
                meta['brand'], meta['sector'], domain, n=20
            )

        # Run all SERP checks in parallel
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_serp_check, test_queries))

        for query, organic in results:
            domain_found = False
            for item in organic:
                link = (item.get('link') or '').lower()
                host = link.split('://', 1)[-1].split('/', 1)[0]
                if host.startswith('www.'):
                    host = host[4:]

                if host == domain:
                    domain_found = True
                    domain_keywords.add(query)

                if host in competitors and not domain_found:
                    if query not in competitor_keywords:
                        competitor_keywords[query] = {
                            'keyword': query,
                            'competitor': host,
                            'position': item.get('position', 0),
                            'url': item.get('link', ''),
                            'title': item.get('title', ''),
                        }

        # Step 4: filter to gaps (competitor has it, domain does not)
        gaps = [
            v for k, v in competitor_keywords.items()
            if k not in domain_keywords
        ]

        # Step 5: estimate opportunity scores
        from .keyword_intent import classify_intent
        for gap in gaps:
            intent = classify_intent(gap['keyword'])
            gap['intent'] = intent
            # Opportunity score formula
            commercial_boost = 1.3 if intent in ('commercial', 'transactional') else 1.0
            position_factor = max(0, (20 - gap.get('position', 20)) / 20)
            gap['opportunity_score'] = round(
                min(100, position_factor * 60 * commercial_boost + 30)
            )

        # Sort by opportunity score
        gaps.sort(key=lambda g: g.get('opportunity_score', 0), reverse=True)

        # Estimate total monthly searches (rough)
        estimated_monthly_searches = len(gaps) * 320  # rough avg

        payload = {
            'domain': domain,
            'brand': meta['brand'],
            'sector': meta['sector'],
            'analyzed_at': datetime.utcnow().isoformat(),
            'competitors_detected': competitors,
            'total_gaps': len(gaps),
            'estimated_monthly_searches': estimated_monthly_searches,
            'top_opportunities': [
                {
                    'keyword': g['keyword'],
                    'competitor': g['competitor'],
                    'position': g['position'],
                    'intent': g.get('intent', 'informational'),
                    'opportunity_score': g.get('opportunity_score', 0),
                }
                for g in gaps[:5]
            ],
            'gated': {
                'all_opportunities': [
                    {
                        'keyword': g['keyword'],
                        'competitor': g['competitor'],
                        'position': g['position'],
                        'url': g.get('url', ''),
                        'title': g.get('title', ''),
                        'intent': g.get('intent', 'informational'),
                        'opportunity_score': g.get('opportunity_score', 0),
                    }
                    for g in gaps
                ],
                'remaining_count': max(0, len(gaps) - 5),
            },
        }

        from .models import ToolAnalysis
        ToolAnalysis.objects.create(
            domain=domain,
            tool='competitor_gap',
            status='completed',
            score=gaps[0]['opportunity_score'] if gaps else 0,
            result=payload,
            ip=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )

        cache.set(cache_key, payload, timeout=3600)
        return Response(payload)


class PublicToolEventView(APIView):
    """POST /api/public/tool-event/ {event, tool, domain?, metadata?}

    Lightweight conversion event tracking for all public tools.
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PublicToolThrottle]

    def post(self, request):
        event = request.data.get('event', '')
        tool = request.data.get('tool', '')
        if not event:
            return Response(
                {'error': 'event is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from .models import ConversionEvent
        ConversionEvent.objects.create(
            event=event,
            tool=tool,
            domain=request.data.get('domain', ''),
            metadata=request.data.get('metadata', {}),
            ip=_get_client_ip(request),
        )
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


def _normalize_can_i_rank(payload: dict) -> dict:
    """Coerce the LLM output into the EXACT shape CanIRankChecker (frontend)
    expects, so a shape drift (factors as dict, verdict in English, string
    competitors/quick_wins) never crashes the frontend .map() calls."""
    if not isinstance(payload, dict):
        payload = {}
    vmap = {'easy': 'Facile', 'possible': 'Possible',
            'difficult': 'Difficile', 'very_difficult': 'Tres difficile'}
    fr = set(vmap.values())
    v = str(payload.get('verdict', '')).strip()
    payload['verdict'] = v if v in fr else vmap.get(v.lower(), 'Possible')
    labels = {
        'domain_authority_estimate': "Autorite du domaine",
        'content_relevance': "Pertinence du contenu",
        'competition_level': "Niveau de competition",
        'topical_authority': "Autorite thematique",
        'technical_readiness': "Preparation technique",
    }
    f = payload.get('factors')
    if isinstance(f, dict):
        payload['factors'] = [
            {'name': labels.get(k, str(k).replace('_', ' ').capitalize()),
             'score': int(val) if isinstance(val, (int, float)) else 0}
            for k, val in f.items()
        ]
    elif not isinstance(f, list):
        payload['factors'] = []
    qw = payload.get('quick_wins')
    payload['quick_wins'] = [
        (i if isinstance(i, dict) else {'title': str(i), 'description': ''})
        for i in (qw if isinstance(qw, list) else [])
    ]
    tc = payload.get('top_competitors')
    payload['top_competitors'] = [
        (i if isinstance(i, dict) else {'domain': str(i), 'authority': 0})
        for i in (tc if isinstance(tc, list) else [])
    ]
    if not isinstance(payload.get('overall_score'), (int, float)):
        payload['overall_score'] = 0
    payload.setdefault('estimated_time_to_rank', '-')
    return payload


class PublicCanIRankView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PublicToolThrottle]

    def post(self, request):
        domain = request.data.get('domain', '')
        keyword = request.data.get('keyword', '')
        
        domain_norm = _normalize_domain(domain)
        if not domain_norm or not keyword:
            return Response({'error': 'invalid domain or keyword'}, status=status.HTTP_400_BAD_REQUEST)
            
        import re
        keyword_slug = re.sub(r'[^a-z0-9]+', '-', keyword.lower()).strip('-')
        cache_key = f'can_i_rank:{domain_norm}:{keyword_slug}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
            
        crawl = _crawl_homepage_light(f'https://{domain_norm}')
        
        gemini_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_key:
            return Response({'error': 'AI not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        prompt = (
            f"Analyse if the website {domain_norm} can realistically rank for the keyword '{keyword}'.\n"
            f"Here is some info about the site's homepage: Title: {crawl.get('title')}, H1: {crawl.get('h1')}, Desc: {crawl.get('meta_description')}\n"
            f"Act as an expert SEO. Return a realistic assessment. Provide the result in JSON format EXACTLY matching this structure:\n"
            "Repond en francais canadien. Output ONLY JSON matching EXACTLY:\n"
            "{\n"
            '  "overall_score": <number 0-100>,\n'
            '  "verdict": "<Facile|Possible|Difficile|Tres difficile>",\n'
            '  "factors": [\n'
            '    {"name": "Autorite du domaine", "score": <0-100>},\n'
            '    {"name": "Pertinence du contenu", "score": <0-100>},\n'
            '    {"name": "Niveau de competition", "score": <0-100>},\n'
            '    {"name": "Autorite thematique", "score": <0-100>},\n'
            '    {"name": "Preparation technique", "score": <0-100>}\n'
            "  ],\n"
            '  "quick_wins": [\n'
            '    {"title": "<court>", "description": "<une phrase>"},\n'
            '    {"title": "<court>", "description": "<une phrase>"},\n'
            '    {"title": "<court>", "description": "<une phrase>"}\n'
            "  ],\n"
            '  "top_competitors": [\n'
            '    {"domain": "<domaine1.com>", "authority": <0-100>},\n'
            '    {"domain": "<domaine2.com>", "authority": <0-100>},\n'
            '    {"domain": "<domaine3.com>", "authority": <0-100>}\n'
            "  ],\n"
            '  "estimated_time_to_rank": "<ex: 3-6 mois>"\n'
            "}\n"
            "No markdown, only the JSON."
        )
        
        import requests as http_requests
        try:
            r = http_requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}',
                json={
                    'contents': [{'parts': [{'text': prompt}]}],
                    'generationConfig': {'thinkingConfig': {'thinkingBudget': 0}},
                },
                timeout=25,
            )
            r.raise_for_status()
            text = r.json()['candidates'][0]['content']['parts'][0]['text']
            
            text = text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            if text.startswith('json'):
                text = text[4:].strip()
                
            payload = _normalize_can_i_rank(json.loads(text))
            payload['domain'] = domain_norm
            payload['keyword'] = keyword

            cache.set(cache_key, payload, timeout=3600)
            return Response(payload)
        except Exception:
            logger.exception('CanIRank failed')
            return Response({'error': 'AI analysis failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PublicSeoRoiCalculatorView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PublicToolThrottle]

    def post(self, request):
        domain = request.data.get('domain', '')
        domain_norm = _normalize_domain(domain)
        if not domain_norm:
            return Response({'error': 'invalid domain'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            monthly_traffic = float(request.data.get('monthly_traffic', 1000))
            avg_conversion_rate = float(request.data.get('avg_conversion_rate', 2.5)) / 100.0
            avg_deal_value = float(request.data.get('avg_deal_value', 500))
            monthly_seo_investment = float(request.data.get('monthly_seo_investment', 1000))
        except (ValueError, TypeError):
            return Response({'error': 'invalid numeric inputs'}, status=status.HTTP_400_BAD_REQUEST)
            
        def _calc_scenario(base_traffic, months, boost_rate, normal_rate):
            data = []
            current_traffic = base_traffic
            cum_rev = 0
            for i in range(1, months + 1):
                rate = boost_rate if i <= 3 else normal_rate
                current_traffic = current_traffic * (1 + rate)
                leads = current_traffic * avg_conversion_rate
                rev = leads * avg_deal_value
                cum_rev += rev
                cost = monthly_seo_investment * i
                roi = ((cum_rev - cost) / cost * 100) if cost > 0 else 0
                data.append({
                    'month': i,
                    'projected_traffic': int(current_traffic),
                    'projected_leads': int(leads),
                    'projected_revenue': round(rev, 2),
                    'cumulative_revenue': round(cum_rev, 2),
                    'roi_percentage': round(roi, 2)
                })
            totals = {
                'traffic_added': int(current_traffic - base_traffic),
                'total_leads': sum(d['projected_leads'] for d in data),
                'total_revenue': round(cum_rev, 2),
                'total_cost': round(monthly_seo_investment * months, 2),
            }
            return {'monthly_projections': data, 'totals': totals}

        scenarios = {
            'conservative': _calc_scenario(monthly_traffic, 12, 0.15, 0.08),
            'moderate': _calc_scenario(monthly_traffic, 12, 0.25, 0.12),
            'aggressive': _calc_scenario(monthly_traffic, 12, 0.40, 0.18),
        }
        
        break_even_month = None
        for m in scenarios['moderate']['monthly_projections']:
            if m['roi_percentage'] > 0:
                break_even_month = m['month']
                break
                
        year_one_roi_percent = scenarios['moderate']['monthly_projections'][-1]['roi_percentage']

        # Reshape each scenario into the EXACT shape SeoRoiCalculator (frontend)
        # reads: {name, year_one_revenue, roi_percent, break_even_month,
        # monthly_revenue[]}. The frontend did scenarios.moderate.monthly_revenue
        # .map() on a payload that only had monthly_projections -> TypeError.
        def _summary(sc, label):
            proj = sc.get('monthly_projections', [])
            be = next((m['month'] for m in proj if m['roi_percentage'] > 0), 12)
            return {
                'name': label,
                'year_one_revenue': round(sc.get('totals', {}).get('total_revenue', 0)),
                'roi_percent': round(proj[-1]['roi_percentage']) if proj else 0,
                'break_even_month': be,
                'monthly_revenue': [round(m['projected_revenue']) for m in proj],
                'monthly_projections': proj,
                'totals': sc.get('totals', {}),
            }
        scenarios = {
            'conservative': _summary(scenarios['conservative'], 'Conservateur'),
            'moderate': _summary(scenarios['moderate'], 'Modere'),
            'aggressive': _summary(scenarios['aggressive'], 'Agressif'),
        }

        insight = f"Avec un investissement de {monthly_seo_investment}$/mois, le scenario modere prevoit un ROI positif au mois {break_even_month if break_even_month else '12+'}."
        gridar_advantage = "Gridar automatise la creation de contenu a grande echelle, ce qui permet d'atteindre le scenario agressif pour une fraction du cout d'une agence."
        
        payload = {
            'domain': domain_norm,
            'inputs': {
                'monthly_traffic': monthly_traffic,
                'avg_conversion_rate': request.data.get('avg_conversion_rate', 2.5),
                'avg_deal_value': avg_deal_value,
                'monthly_seo_investment': monthly_seo_investment
            },
            'scenarios': scenarios,
            'break_even_month': break_even_month,
            'year_one_roi_percent': year_one_roi_percent,
            'insight': insight,
            'gridar_advantage': gridar_advantage
        }
        return Response(payload)


class PublicAiCitationCheckerView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PublicToolThrottle]

    def post(self, request):
        domain = request.data.get('domain', '')
        domain_norm = _normalize_domain(domain)
        if not domain_norm:
            return Response({'error': 'invalid domain'}, status=status.HTTP_400_BAD_REQUEST)
            
        cache_key = f'ai_citation:{domain_norm}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
            
        crawl = _crawl_homepage_light(f'https://{domain_norm}')
        brand_info = _marque_et_secteur(crawl, domain_norm)

        # DeepSeek d'abord, en lisant la page reelle ; repli sur le
        # generateur par secteur seulement si le LLM echoue.
        queries = _requetes_commerciales_llm(crawl, brand_info['brand'], domain_norm, n=8)
        if not queries:
            queries = _generate_commercial_queries(brand_info['brand'], brand_info['sector'], domain_norm, n=8)
        if not queries:
            queries = [f"meilleur {brand_info['sector']} Montreal", f"comparatif {brand_info['sector']}"]
            
        gemini_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_key:
            return Response({'error': 'AI not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        import requests as http_requests
        
        def check_query(q):
            prompt = (
                f"User asks: {q}\n"
                f"Please provide a short factual answer, and importantly, list exactly 3 domain names as sources/citations for your answer. "
                f"Return ONLY a JSON object:\n"
                f"{{\n"
                f'  "answer": "<short text>",\n'
                f'  "sources": ["<domain1.com>", "<domain2.com>", "<domain3.com>"]\n'
                f"}}\n"
            )
            try:
                r = http_requests.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}',
                    json={'contents': [{'parts': [{'text': prompt}]}]},
                    timeout=15,
                )
                r.raise_for_status()
                text = r.json()['candidates'][0]['content']['parts'][0]['text']
                text = text.strip()
                if text.startswith('```'):
                    text = text.split('\n', 1)[1] if '\n' in text else text[3:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
                if text.startswith('json'):
                    text = text[4:].strip()
                parsed = json.loads(text)
                return q, parsed
            except Exception:
                return q, None
                
        results = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(check_query, q) for q in queries]
            for future in as_completed(futures):
                q, res = future.result()
                if res:
                    sources = [s.lower() for s in res.get('sources', [])]
                    cited = any(domain_norm in s for s in sources)
                    results.append({
                        'query': q,
                        'cited': cited,
                        'context_snippet': res.get('answer', ''),
                        'competing_sources': sources
                    })
                    
        total_queries = len(results)
        times_cited = sum(1 for r in results if r['cited'])
        score = int((times_cited / total_queries * 100)) if total_queries > 0 else 0
        
        all_competitors = []
        for r in results:
            if not r['cited']:
                all_competitors.extend([s for s in r['competing_sources'] if domain_norm not in s])
                
        from collections import Counter
        top_competing = [{'domain': c[0], 'count': c[1]} for c in Counter(all_competitors).most_common(5)]
        
        payload = {
            'domain': domain_norm,
            'citation_score': score,
            'total_queries_tested': total_queries,
            'times_cited': times_cited,
            'results': results,
            'citation_results': results,
            'top_competing_sources': top_competing,
            'recommendations': [
                "Publiez des donnees originales et des statistiques propres a votre secteur.",
                "Creez des pages comparatives objectives et detaillees.",
                "Optimisez vos titres pour repondre directement aux questions de votre audience."
            ],
            'gridar_advantage': "Gridar construit des cocons semantiques de haute qualite qui positionnent votre site comme une reference pour l'IA."
        }
        cache.set(cache_key, payload, timeout=3600)
        return Response(payload)


class PublicCompetitorCompareView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [PublicToolThrottle]

    def post(self, request):
        domain = request.data.get('domain', '')
        competitor = request.data.get('competitor', '')
        
        domain_norm = _normalize_domain(domain)
        comp_norm = _normalize_domain(competitor)
        
        if not domain_norm or not comp_norm:
            return Response({'error': 'invalid domains'}, status=status.HTTP_400_BAD_REQUEST)
            
        cache_key = f'competitor_compare:{domain_norm}:{comp_norm}'
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)
            
        d_crawl = _crawl_homepage_light(f'https://{domain_norm}')
        c_crawl = _crawl_homepage_light(f'https://{comp_norm}')
        
        gemini_key = os.environ.get('GEMINI_API_KEY')
        if not gemini_key:
            return Response({'error': 'AI not configured'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        prompt = (
            f"Compare these two domains for SEO and online presence:\n"
            f"Domain 1: {domain_norm}\n"
            f"Info: Title: {d_crawl.get('title')}, H1: {d_crawl.get('h1')}, Desc: {d_crawl.get('meta_description')}\n\n"
            f"Domain 2: {comp_norm}\n"
            f"Info: Title: {c_crawl.get('title')}, H1: {c_crawl.get('h1')}, Desc: {c_crawl.get('meta_description')}\n\n"
            f"Return a JSON analysis EXACTLY matching this structure:\n"
            "{\n"
            f'  "overall_winner": "<{domain_norm} or {comp_norm}>",\n'
            '  "categories": [\n'
            '    {"category": "SEO technique", "domain_score": <0-100>, "competitor_score": <0-100>, "winner": "<domain>", "insight": "<courte remarque>"},\n'
            '    {"category": "Contenu", "domain_score": <0-100>, "competitor_score": <0-100>, "winner": "<domain>", "insight": "<courte remarque>"},\n'
            '    {"category": "Autorite percue", "domain_score": <0-100>, "competitor_score": <0-100>, "winner": "<domain>", "insight": "<courte remarque>"},\n'
            '    {"category": "UX et design", "domain_score": <0-100>, "competitor_score": <0-100>, "winner": "<domain>", "insight": "<courte remarque>"},\n'
            '    {"category": "Presence IA", "domain_score": <0-100>, "competitor_score": <0-100>, "winner": "<domain>", "insight": "<courte remarque>"},\n'
            '    {"category": "Strategie locale", "domain_score": <0-100>, "competitor_score": <0-100>, "winner": "<domain>", "insight": "<courte remarque>"}\n'
            '  ],\n'
            '  "summary": "<paragraphe en francais canadien>",\n'
            '  "domain_advantages": ["<avantage 1>", "<avantage 2>"],\n'
            '  "competitor_advantages": ["<avantage 1>", "<avantage 2>"],\n'
            '  "action_items": [\n'
            '    {"priority": "<Haute|Moyenne|Basse>", "text": "<action>"},\n'
            '    {"priority": "<Haute|Moyenne|Basse>", "text": "<action>"},\n'
            '    {"priority": "<Haute|Moyenne|Basse>", "text": "<action>"}\n'
            '  ],\n'
            '  "gridar_advantage": "<short sentence in French Canadian>"\n'
            "}\n"
            "Do NOT include markdown formatting, output raw JSON."
        )
        
        import requests as http_requests
        try:
            r = http_requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}',
                json={
                    'contents': [{'parts': [{'text': prompt}]}],
                    'generationConfig': {'thinkingConfig': {'thinkingBudget': 0}},
                },
                timeout=25,
            )
            r.raise_for_status()
            text = r.json()['candidates'][0]['content']['parts'][0]['text']
            
            text = text.strip()
            if text.startswith('```'):
                text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            if text.startswith('json'):
                text = text[4:].strip()
                
            payload = json.loads(text)
            # Normalize to the CompetitorCompare (frontend) contract, whatever the
            # LLM returns: categories[].category, flat *_advantages, action_items
            # as {priority, text}. Frontend does .map on these -> must be arrays.
            cats = payload.get('categories')
            if isinstance(cats, list):
                for c in cats:
                    if isinstance(c, dict) and not c.get('category'):
                        c['category'] = c.get('name', '')
            else:
                payload['categories'] = []
            ka = payload.get('key_advantages')
            if isinstance(ka, dict):
                payload.setdefault('domain_advantages', ka.get('domain', []))
                payload.setdefault('competitor_advantages', ka.get('competitor', []))
            if not isinstance(payload.get('domain_advantages'), list):
                payload['domain_advantages'] = []
            if not isinstance(payload.get('competitor_advantages'), list):
                payload['competitor_advantages'] = []
            ai = payload.get('action_items')
            payload['action_items'] = [
                (i if isinstance(i, dict) else {'priority': 'Moyenne', 'text': str(i)})
                for i in (ai if isinstance(ai, list) else [])
            ]
            payload['domain'] = domain_norm
            payload['competitor'] = comp_norm

            cache.set(cache_key, payload, timeout=3600)
            return Response(payload)
        except Exception:
            logger.exception('CompetitorCompare failed')
            return Response({'error': 'AI analysis failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
