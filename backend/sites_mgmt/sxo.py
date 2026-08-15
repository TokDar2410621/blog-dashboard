"""SXO page-type taxonomy: classify a page, then compare it to the SERP.

Ported from claude-seo v2.2.4 `skills/seo-sxo/SKILL.md` and
`skills/seo-sxo/references/page-type-taxonomy.md`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream ships the taxonomy as prose for a human or an LLM to apply page by
page. This port turns it into a deterministic scorer over raw HTML so the
backend can run it on every audited page without an API round trip. Three
adaptations. The 8 upstream types become 9: `Hybrid` was a SaaS-specific blend
that reads better here as a flag on the winning type, while `guide`, `categorie`
and `accueil` had to be added because upstream files all three under Blog Post
and Gridar publishes them daily. `Landing Page` and `Service Page` are merged
into `landing_service`, since the same Quebec page sells a service and asks for
a soumission. Every signal list is doubled in French: an English-only matcher
scores a Laval plumber's page at zero, which is worse than not running at all.

The severity table in `detect_mismatch` is upstream's, extended with the
per-type "Common mismatches" lines from the taxonomy reference. Public output
is French because it reaches Gridar users; code and comments stay English.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlparse

__all__ = [
    'TYPES_PAGE',
    'LIBELLES_TYPES',
    'FAMILLES_TYPES',
    'classify_page_type',
    'detect_mismatch',
    'normalize_page_type',
]


TYPES_PAGE = (
    'accueil',
    'article',
    'guide',
    'comparatif',
    'landing_service',
    'fiche_produit',
    'categorie',
    'page_locale',
    'outil',
)

LIBELLES_TYPES = {
    'accueil': "Page d'accueil",
    'article': 'Article',
    'guide': 'Guide',
    'comparatif': 'Comparatif',
    'landing_service': 'Landing service',
    'fiche_produit': 'Fiche produit',
    'categorie': 'Page catégorie',
    'page_locale': 'Page locale',
    'outil': 'Outil',
}

# Two types of the same family answer roughly the same intent, so ranking one
# where Google shows the other is a format problem, not a wall.
FAMILLES_TYPES = {
    'accueil': 'navigation',
    'categorie': 'navigation',
    'article': 'informationnel',
    'guide': 'informationnel',
    'comparatif': 'commercial',
    'landing_service': 'transactionnel',
    'fiche_produit': 'transactionnel',
    'page_locale': 'local',
    'outil': 'outil',
}

# Upstream's "Classification Priority" (tool > local > comparison > product >
# landing > service > hybrid > blog), with the three Gridar types slotted in.
# `accueil` sits high because a root URL cannot be repurposed without collateral
# damage, so knowing it is the homepage outranks knowing it looks like a landing.
_PRIORITE = (
    'outil',
    'accueil',
    'page_locale',
    'comparatif',
    'fiche_produit',
    'categorie',
    'landing_service',
    'guide',
    'article',
)

# Two types within this many points count as tied, and priority decides.
_MARGE_EGALITE = 0.5

# Enough weight on the winner to call the evidence complete.
_PLEINE_PREUVE = 6.0

_SEVERITES = ('aucune', 'faible', 'moyenne', 'elevee', 'critique')

_MAX_HTML = 3_000_000


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def _plat(valeur) -> str:
    """Lowercase, accent-free, whitespace-collapsed form used by every matcher.

    Quebec pages mix "diplômé" and "diplome" freely, sometimes in the same
    paragraph, and CMS exports mangle apostrophes. Matching on the flattened
    form is the only way a single pattern catches both spellings.
    """
    if not valeur:
        return ''
    texte = str(valeur).replace('’', "'").replace('ʼ', "'")
    texte = texte.replace('œ', 'oe').replace('Œ', 'OE')
    texte = texte.replace('æ', 'ae').replace('Æ', 'AE')
    texte = unicodedata.normalize('NFD', texte)
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return ' '.join(texte.lower().split())


# ---------------------------------------------------------------------------
# HTML reading
# ---------------------------------------------------------------------------

# Text inside these never describes the page to a reader.
_SKIP_TAGS = frozenset({'script', 'style', 'noscript', 'template', 'svg'})

_CLASSES_CTA = re.compile(r'\b(?:btn|button|cta|bouton)\b|[-_](?:btn|cta)\b')


class _PageParser(HTMLParser):
    """Best-effort structural read. Malformed markup must not lose the page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ''
        self.h1 = []
        self.entetes = []
        self.metas = {}
        self.jsonld = []
        self.itemtypes = []
        self.links = []
        self.ctas = []
        self.iframes = []
        self.rels = set()
        self.input_types = Counter()
        self.tags = Counter()
        self.tokens = []
        self.nav_links = 0
        self.text = []
        self._skip = 0
        self._nav = 0
        self._grab = None
        self._buf = []
        self._jsonld_buf = []
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = {}
        for cle, valeur in attrs:
            if cle not in a:
                a[cle] = valeur or ''

        self.tags[tag] += 1
        marqueurs = (a.get('class', '') + ' ' + a.get('id', '')).strip()
        if marqueurs and len(self.tokens) < 3000:
            self.tokens.append(marqueurs.lower())

        rel = (a.get('rel') or '').lower()
        if rel:
            self.rels.update(rel.replace(',', ' ').split())

        itemtype = (a.get('itemtype') or '').rstrip('/')
        if itemtype:
            self.itemtypes.append(itemtype.rsplit('/', 1)[-1].lower())

        if tag in _SKIP_TAGS:
            self._skip += 1

        if tag == 'script':
            if 'ld+json' in (a.get('type') or '').lower():
                self._in_jsonld = True
                self._jsonld_buf = []
        elif tag == 'title':
            self._start_grab('title')
        elif tag == 'h1':
            self._start_grab('h1')
        elif tag in ('h2', 'h3'):
            self._start_grab(tag)
        elif tag == 'button':
            self._start_grab('cta')
        elif tag == 'meta':
            cle = (a.get('name') or a.get('property') or a.get('itemprop') or '').lower()
            if cle:
                self.metas[cle] = a.get('content') or ''
        elif tag == 'a':
            self.links.append(a.get('href') or '')
            if self._nav:
                self.nav_links += 1
            if _CLASSES_CTA.search((a.get('class') or '').lower()):
                self._start_grab('cta')
        elif tag == 'input':
            type_champ = (a.get('type') or 'text').lower()
            self.input_types[type_champ] += 1
            if type_champ in ('submit', 'button') and a.get('value'):
                self.ctas.append(a['value'])
        elif tag == 'iframe':
            self.iframes.append((a.get('src') or '').lower())
        elif tag == 'nav':
            self._nav += 1
        elif tag == 'time' and a.get('datetime'):
            self.tags['time_datetime'] += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        if tag == 'nav' and self._nav:
            self._nav -= 1

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        if tag == 'script' and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld.append(''.join(self._jsonld_buf))
        if tag == 'nav' and self._nav:
            self._nav -= 1
        if not self._grab:
            return
        ferme = tag == self._grab or (self._grab == 'cta' and tag in ('a', 'button'))
        if not ferme:
            return
        valeur = ' '.join(''.join(self._buf).split())
        if self._grab == 'title':
            if not self.title:
                self.title = valeur
        elif self._grab == 'h1':
            self.h1.append(valeur)
        elif self._grab in ('h2', 'h3'):
            self.entetes.append(valeur)
        elif valeur:
            self.ctas.append(valeur)
        self._grab = None
        self._buf = []

    def handle_data(self, data):
        if self._in_jsonld:
            self._jsonld_buf.append(data)
            return
        if self._grab:
            self._buf.append(data)
        if not self._skip and len(self.text) < 20000:
            self.text.append(data)

    def _start_grab(self, cle):
        self._grab = cle
        self._buf = []


def _walk_types(noeud, sortie, profondeur=0):
    """Collect every @type in a JSON-LD tree, @graph and nested nodes included."""
    if profondeur > 6:
        return
    if isinstance(noeud, dict):
        brut = noeud.get('@type')
        if isinstance(brut, str):
            sortie.add(brut.lower())
        elif isinstance(brut, list):
            sortie.update(str(x).lower() for x in brut)
        for valeur in noeud.values():
            _walk_types(valeur, sortie, profondeur + 1)
    elif isinstance(noeud, list):
        for valeur in noeud[:80]:
            _walk_types(valeur, sortie, profondeur + 1)


def _parse_html(html: str) -> dict:
    parser = _PageParser()
    try:
        parser.feed((html or '')[:_MAX_HTML])
        parser.close()
    except Exception:
        # Audited sites ship broken markup constantly. Keep whatever was read
        # before the failure instead of throwing the page away.
        pass

    schemas = set()
    for brut in parser.jsonld:
        try:
            _walk_types(json.loads(brut), schemas)
        except (ValueError, TypeError, RecursionError):
            continue
    schemas.update(parser.itemtypes)

    titre = _plat(parser.title)
    h1 = _plat(' '.join(parser.h1))
    entetes = [_plat(e) for e in parser.entetes]
    texte = _plat(' '.join(parser.text))

    return {
        'titre': (titre + ' ' + h1).strip(),
        'titre_brut': parser.title,
        'entetes': entetes,
        'texte': texte,
        'mots': len(texte.split()),
        'ctas': _plat(' '.join(parser.ctas)),
        'schemas': schemas,
        'metas': {k: _plat(v) for k, v in parser.metas.items()},
        'liens': list(dict.fromkeys(parser.links)),
        'tags': parser.tags,
        'input_types': parser.input_types,
        'tokens': _plat(' '.join(parser.tokens)),
        'rels': parser.rels,
        'iframes': parser.iframes,
        'liens_nav': parser.nav_links,
    }


# ---------------------------------------------------------------------------
# Signal patterns (FR-CA first, English kept so ported sites still score)
# ---------------------------------------------------------------------------

_VILLES_QC = (
    'montreal', 'quebec', 'laval', 'gatineau', 'sherbrooke', 'trois-rivieres',
    'longueuil', 'levis', 'saguenay', 'chicoutimi', 'jonquiere', 'granby',
    'drummondville', 'saint-jerome', 'saint-hyacinthe', 'shawinigan', 'joliette',
    'rimouski', 'victoriaville', 'rouyn-noranda', 'val-d\'or', 'sept-iles',
    'terrebonne', 'brossard', 'repentigny', 'blainville', 'boucherville',
    'mascouche', 'mirabel', 'vaudreuil', 'saint-eustache', 'salaberry',
    'saint-jean-sur-richelieu', 'beloeil', 'sorel-tracy', 'magog', 'alma',
    'rive-sud', 'rive-nord', 'monteregie', 'lanaudiere', 'laurentides',
    'outaouais', 'estrie', 'mauricie', 'abitibi', 'gaspesie', 'charlevoix',
)
_RE_VILLE = re.compile(r'\b(?:' + '|'.join(re.escape(v) for v in _VILLES_QC) + r')\b')

_RE_CTA_VENTE = re.compile(
    r"ajouter au panier|ajout au panier|mettre au panier|add to cart|"
    r"acheter maintenant|achetez maintenant|buy now|commander maintenant|"
    r"passer la commande|proceder au paiement|finaliser ma commande|checkout"
)
_RE_STOCK = re.compile(
    r"en stock|rupture de stock|stock limite|derniers articles|disponibilite|"
    r"expedie sous|livraison gratuite|ramassage en magasin|cueillette en magasin|"
    r"retour gratuit|garantie \d+ ans"
)
_RE_SKU = re.compile(
    r"\b(?:sku|ugs|upc|ean|no de modele|numero de modele|code produit|"
    r"reference produit|no de piece)\b"
)
# Quebec prices put the sign last (39,99 $) and US ones first ($39.99).
_RE_PRIX = re.compile(
    r"\d[\d ]*[,.]\d{2}\s*\$|\$\s?\d[\d ]*(?:[.,]\d{2})?|\b\d[\d ]*\s?\$"
)
_RE_COMPARATIF = re.compile(
    r"\bvs\b|\bversus\b|comparatif|comparaison|comparons|face a face|"
    r"lequel choisir|laquelle choisir|avantages et inconvenients|pour et contre|"
    r"points forts et points faibles|notre verdict|tableau comparatif|"
    r"grille comparative|alternative a |alternatives a |meilleure alternative"
)
_RE_TOP_LISTE = re.compile(
    r"\btop\s*\d+\b|\b\d+\s+meilleur|\bles meilleurs?\b|\bles meilleures?\b|"
    r"palmares|classement des|selection des"
)
_RE_GUIDE_TITRE = re.compile(
    r"^(?:comment|guide|le guide|tutoriel|tuto|apprendre a)\b|guide complet|"
    r"guide ultime|guide pratique|tout savoir sur|tout ce que|de a a z|"
    r"\ben \d+ etapes\b|etape par etape|pas a pas|mode d'emploi|checklist|"
    r"liste de verification|marche a suivre|how to\b"
)
_RE_ETAPE = re.compile(r"^(?:etape|step)\s*\d|^\d+[.)]\s|^\d+\s*[-.]\s*[a-z]")
_RE_SOMMAIRE = re.compile(
    r"table des matieres|sommaire|dans cet article|au menu de cet article|"
    r"ce que vous allez apprendre"
)
_RE_BYLINE = re.compile(
    r"ecrit par|redige par|par l'equipe|publie le|publie par|mis a jour le|"
    r"derniere mise a jour|temps de lecture|min de lecture|minutes de lecture"
)
_RE_BLOG_UX = re.compile(
    r"articles similaires|a lire aussi|sur le meme sujet|articles connexes|"
    r"lire aussi|partager cet article|laisser un commentaire|"
    r"abonnez-vous a l'infolettre|inscrivez-vous a notre infolettre"
)
_RE_CTA_SERVICE = re.compile(
    r"demander une soumission|obtenir une soumission|demande de soumission|"
    r"soumission gratuite|demander un devis|obtenir un devis|devis gratuit|"
    r"prendre rendez-vous|reserver une consultation|consultation gratuite|"
    r"estimation gratuite|evaluation gratuite|parlez a un expert|"
    r"contactez-nous|appelez-nous|essai gratuit|essayer gratuitement|"
    r"reserver une demo|demander une demo|voir la demo|commencer gratuitement|"
    r"planifier un appel|obtenir mon acces|s'inscrire maintenant|get started"
)
_RE_PREUVE_SERVICE = re.compile(
    r"nos services|notre processus|comment ca marche|nos realisations|"
    r"etude de cas|etudes de cas|temoignages|avis de nos clients|"
    r"ce que disent nos clients|pourquoi nous choisir|nos forfaits|nos tarifs|"
    r"notre equipe|nos garanties|clients satisfaits|deja \d+ clients|"
    r"ils nous font confiance"
)
_RE_LOCAL = re.compile(
    r"heures d'ouverture|nous joindre|nous trouver|ou nous trouver|itineraire|"
    r"obtenir l'itineraire|voir sur la carte|zone desservie|zones desservies|"
    r"secteurs desservis|nous desservons|sur rendez-vous|notre adresse|"
    r"notre succursale|nos succursales|stationnement gratuit|"
    r"desservons la region|service a domicile"
)
_RE_OUTIL_TITRE = re.compile(
    r"calculateur|calculatrice|simulateur|generateur|verificateur|convertisseur|"
    r"estimateur|analyseur|\boutil\b|\boutils\b|calculator|generator|checker|"
    r"\bquiz\b|audit gratuit|test gratuit"
)
_RE_OUTIL_UX = re.compile(
    r"entrez votre|entrez vos|saisissez|indiquez votre|remplissez les champs|"
    r"\bcalculer\b|\bestimer\b|\bconvertir\b|\bgenerer\b|\banalyser\b|"
    r"voir le resultat|obtenir mon resultat|resultat instantane|"
    r"resultats? en \d+ secondes"
)
_RE_CATEGORIE = re.compile(
    r"nos articles|tous nos articles|voir tous les|voir toutes les|"
    r"derniers articles|articles recents|archives|resultats pour|"
    r"articles classes|filtrer par|trier par|page \d+ (?:sur|de) \d+|"
    r"afficher plus|charger plus|articles suivants"
)
_RE_ACCUEIL = re.compile(r"\baccueil\b|bienvenue (?:chez|sur|a)|page d'accueil")
_RE_CP_CA = re.compile(r"\b[a-z]\d[a-z][ -]?\d[a-z]\d\b")
_RE_TEL = re.compile(r"(?:\+?1[ .-]?)?\(?\b\d{3}\)?[ .-]?\d{3}[ .-]?\d{4}\b")
_RE_SLUG_VS = re.compile(r"(?:^|-)(?:vs|versus)(?:-|$)")
# Class and id names of a calculator's output container.
_RE_ZONE_RESULTAT = re.compile(
    r"\bresultat|\boutput\b|\bcalculator\b|\bcalculateur\b|\bsimulateur\b"
)
_RE_PAGE_N = re.compile(r"\bpage[ /-]?\d+\b|\bpaged?=\d+")

_SCHEMAS_ARTICLE = frozenset({
    'article', 'blogposting', 'newsarticle', 'techarticle', 'scholarlyarticle',
    'liveblogposting', 'advertisercontentarticle',
})
_SCHEMAS_PRODUIT = frozenset({
    'product', 'productgroup', 'productmodel', 'offer', 'aggregateoffer',
})
_SCHEMAS_LOCAL = frozenset({
    'localbusiness', 'restaurant', 'store', 'plumber', 'electrician', 'dentist',
    'physician', 'autorepair', 'automotivebusiness', 'homeandconstructionbusiness',
    'generalcontractor', 'roofingcontractor', 'hvacbusiness', 'movingcompany',
    'realestateagent', 'legalservice', 'attorney', 'medicalclinic', 'hairsalon',
    'healthandbeautybusiness', 'foodestablishment', 'lodgingbusiness',
    'childcare', 'daycare', 'veterinarycare', 'travelagency', 'insuranceagency',
})

# Plural container words. As the LAST URL segment they mark an index, not a
# leaf page: /blogue/ lists posts, /blogue/mon-texte is the post. Singular words
# stay out of this list because /outils/calculateur is a tool, not an index.
_MOTS_INDEX = frozenset({
    'blogue', 'blog', 'articles', 'nouvelles', 'actualites', 'news', 'magazine',
    'guides', 'tutoriels', 'ressources', 'produits', 'products', 'boutique',
    'shop', 'store', 'magasin', 'services', 'solutions', 'offres', 'outils',
    'tools', 'comparatifs', 'categorie', 'categories', 'category', 'tag',
    'tags', 'archives', 'archive', 'collection', 'collections', 'sujets',
    'themes', 'succursales', 'emplacements', 'villes',
})

_SEGMENTS_TYPE = (
    (('blogue', 'blog', 'articles', 'article', 'nouvelles', 'actualites', 'news',
      'magazine', 'carnet'), {'article': 2.0, 'guide': 0.8}),
    (('guide', 'guides', 'tutoriel', 'tutoriels', 'tuto', 'ressources',
      'apprendre', 'how-to', 'howto'), {'guide': 2.0, 'article': 0.8}),
    (('comparatif', 'comparatifs', 'comparaison', 'comparaisons', 'versus', 'vs',
      'alternatives', 'alternative'), {'comparatif': 2.5}),
    (('produit', 'produits', 'product', 'products', 'boutique', 'shop', 'store',
      'magasin'), {'fiche_produit': 2.0}),
    (('service', 'services', 'tarifs', 'tarification', 'prix', 'pricing',
      'forfaits', 'offre', 'offres', 'solutions', 'demo', 'essai', 'soumission',
      'expertise', 'expertises'), {'landing_service': 2.0}),
    (('categorie', 'categories', 'category', 'tag', 'tags', 'sujet', 'sujets',
      'theme', 'thematique', 'archives', 'archive', 'collection', 'collections'),
     {'categorie': 2.5}),
    (('outil', 'outils', 'calculateur', 'calculatrice', 'simulateur',
      'generateur', 'convertisseur', 'verificateur', 'tool', 'tools',
      'calculator'), {'outil': 2.5}),
    (('succursale', 'succursales', 'emplacement', 'emplacements', 'nous-joindre',
      'nous-trouver', 'ou-nous-trouver', 'points-de-vente', 'villes'),
     {'page_locale': 2.0}),
)


def _add(signaux, description, **poids):
    signaux.append({'signal': description, 'poids': {k: float(v) for k, v in poids.items()}})


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

def _signaux_url(ctx, signaux):
    segments = ctx['segments']
    if ctx['racine']:
        if ctx['hote']:
            _add(signaux, "URL à la racine du domaine", accueil=4.0)
        return

    dernier = segments[-1]
    for index, segment in enumerate(segments):
        if index == len(segments) - 1 and segment in _MOTS_INDEX:
            _add(signaux, f"URL se termine par /{segment}/ (page d'index)", categorie=2.5)
            continue
        for mots, poids in _SEGMENTS_TYPE:
            if segment in mots:
                _add(signaux, f"segment d'URL /{segment}/", **poids)

    if _RE_SLUG_VS.search(dernier):
        _add(signaux, "slug d'URL en « x-vs-y »", comparatif=3.0)
    if _RE_VILLE.search(dernier.replace('-', ' ')):
        _add(signaux, "nom de ville québécoise dans le slug", page_locale=1.5)
    if _RE_OUTIL_TITRE.search(dernier.replace('-', ' ')):
        _add(signaux, "slug d'URL d'outil (calculateur, générateur...)", outil=1.5)


def _signaux_schema(doc, ctx, signaux):
    schemas = doc['schemas']
    if schemas & _SCHEMAS_ARTICLE:
        _add(signaux, "schema Article / BlogPosting", article=3.0, guide=1.5)
    if 'howto' in schemas:
        # HowTo lost its rich result in 2023 but still declares the page shape.
        _add(signaux, "schema HowTo", guide=3.0, article=0.5)
    if schemas & _SCHEMAS_PRODUIT:
        _add(signaux, "schema Product / Offer", fiche_produit=3.0)
    if schemas & _SCHEMAS_LOCAL:
        _add(signaux, "schema LocalBusiness (ou sous-type)", page_locale=3.0)
    if 'professionalservice' in schemas:
        _add(signaux, "schema ProfessionalService", landing_service=1.5, page_locale=1.5)
    if 'service' in schemas:
        _add(signaux, "schema Service", landing_service=2.5)
    if 'softwareapplication' in schemas:
        _add(signaux, "schema SoftwareApplication", landing_service=2.0, outil=1.0)
    if 'webapplication' in schemas:
        _add(signaux, "schema WebApplication", outil=3.0)
    if 'collectionpage' in schemas:
        _add(signaux, "schema CollectionPage", categorie=2.5)
    if 'itemlist' in schemas:
        _add(signaux, "schema ItemList", categorie=1.0, comparatif=1.0)
    if schemas & {'aggregaterating', 'review'}:
        _add(signaux, "schema Review / AggregateRating", fiche_produit=1.0, comparatif=0.5)
    if ctx['racine'] and schemas & {'website', 'organization'}:
        _add(signaux, "schema WebSite / Organization sur la racine", accueil=1.5)

    og_type = doc['metas'].get('og:type', '')
    if og_type == 'article':
        _add(signaux, "og:type = article", article=1.5, guide=0.5)
    elif og_type == 'product':
        _add(signaux, "og:type = product", fiche_produit=2.0)
    if doc['metas'].get('article:published_time') or doc['metas'].get('article:modified_time'):
        _add(signaux, "métadonnée article:published_time", article=1.5, guide=0.5)


def _signaux_texte(doc, ctx, signaux):
    titre = doc['titre']
    texte = doc['texte']
    ctas = doc['ctas']
    tout = titre + ' ' + texte + ' ' + ctas

    if _RE_CTA_VENTE.search(tout):
        _add(signaux, "bouton d'achat (panier, acheter maintenant)", fiche_produit=3.0)
    if _RE_PRIX.search(tout):
        if _RE_STOCK.search(tout):
            _add(signaux, "prix affiché avec disponibilité ou livraison", fiche_produit=2.5)
        else:
            _add(signaux, "prix affiché", fiche_produit=1.0, landing_service=0.5)
    if _RE_SKU.search(tout):
        _add(signaux, "identifiant produit (SKU, UGS, no de modèle)", fiche_produit=1.5)

    if _RE_COMPARATIF.search(titre):
        _add(signaux, "titre de comparaison (« vs », comparatif, lequel choisir)", comparatif=3.0)
    elif _RE_COMPARATIF.search(texte):
        _add(signaux, "vocabulaire de comparaison dans le corps", comparatif=1.0)
    if _RE_TOP_LISTE.search(titre):
        _add(signaux, "titre de palmarès (« top N », « les meilleurs »)", comparatif=2.0)

    if _RE_GUIDE_TITRE.search(titre):
        _add(signaux, "titre de guide (comment, guide complet, en N étapes)",
             guide=3.0, article=0.5)
    if _RE_SOMMAIRE.search(texte):
        _add(signaux, "table des matières", guide=1.0, article=0.5)
    if _RE_BYLINE.search(tout):
        _add(signaux, "signature d'auteur ou date de publication", article=2.0, guide=0.8)
    if _RE_BLOG_UX.search(texte):
        _add(signaux, "UX de blogue (articles similaires, partage, commentaires)",
             article=1.5, guide=0.5)

    if _RE_CTA_SERVICE.search(ctas) or _RE_CTA_SERVICE.search(titre):
        _add(signaux, "appel à l'action commercial (soumission, démo, rendez-vous)",
             landing_service=2.5)
    elif _RE_CTA_SERVICE.search(texte):
        _add(signaux, "appel à l'action commercial dans le corps", landing_service=1.5)
    preuves = set(_RE_PREUVE_SERVICE.findall(texte))
    if len(preuves) >= 3:
        _add(signaux, "sections de vente de service (processus, témoignages, forfaits)",
             landing_service=2.0)
    elif preuves:
        _add(signaux, "au moins une section de vente de service", landing_service=1.0)

    if _RE_LOCAL.search(tout):
        _add(signaux, "vocabulaire local (heures d'ouverture, itinéraire, zone desservie)",
             page_locale=1.5)
    if _RE_CP_CA.search(tout) and _RE_TEL.search(tout):
        _add(signaux, "adresse postale canadienne + téléphone (NAP)", page_locale=2.5)
    elif _RE_TEL.search(tout):
        _add(signaux, "numéro de téléphone affiché", page_locale=0.5, landing_service=0.3)
    ville = _RE_VILLE.search(titre)
    if ville:
        _add(signaux, f"ville ou région québécoise dans le titre ({ville.group(0)})",
             page_locale=1.5)

    if _RE_OUTIL_TITRE.search(titre):
        _add(signaux, "titre d'outil (calculateur, générateur, vérificateur)", outil=3.0)
    if _RE_OUTIL_UX.search(tout):
        _add(signaux, "instructions d'utilisation d'un outil", outil=1.0)

    if _RE_CATEGORIE.search(tout) and not ctx['racine']:
        _add(signaux, "vocabulaire de listing (voir tous, filtrer, pagination)", categorie=2.0)
    if ctx['racine'] and _RE_ACCUEIL.search(titre):
        _add(signaux, "titre de page d'accueil", accueil=1.0)


def _liens_enfants(liens, segments):
    """Count links that dive deeper under the page's own first URL segment.

    A listing page points at its children; an article points mostly outward or
    sideways. This is the signal that separates /blogue/ from /blogue/mon-texte.
    """
    if not segments:
        return 0
    prefixe = '/' + segments[0] + '/'
    total = 0
    for href in liens:
        chemin = _plat(urlparse(href).path or '')
        if chemin.startswith(prefixe) and len(chemin) > len(prefixe) + 2:
            total += 1
    return total


def _signaux_structure(doc, ctx, signaux):
    tags = doc['tags']
    champs = doc['input_types']
    mots = doc['mots']

    if tags['table'] >= 1 and tags['th'] >= 3 and tags['tr'] >= 3:
        _add(signaux, "tableau comparatif (au moins 3 colonnes et 3 lignes)", comparatif=2.0)

    interactifs = (
        champs['number'] + champs['range'] + champs['date'] + champs['checkbox']
        + champs['radio'] + tags['select']
    )
    if interactifs >= 2 and (tags['button'] or champs['submit']):
        _add(signaux, "interface interactive (champs de saisie + bouton de calcul)", outil=1.5)
    if _RE_ZONE_RESULTAT.search(doc['tokens']):
        _add(signaux, "zone de résultat dans le balisage", outil=1.5)

    if any('google.com/maps' in src or 'maps.google' in src or 'openstreetmap' in src
           for src in doc['iframes']):
        _add(signaux, "carte intégrée (Google Maps)", page_locale=2.5)
    if tags['address'] >= 1:
        _add(signaux, "balise <address>", page_locale=1.5)

    if not ctx['racine']:
        enfants = _liens_enfants(doc['liens'], ctx['segments'])
        if enfants >= 8 and mots < 900:
            _add(signaux, f"{enfants} liens vers des pages enfants et peu de texte",
                 categorie=3.0)
        elif enfants >= 8:
            _add(signaux, f"{enfants} liens vers des pages enfants", categorie=1.0)
        if tags['article'] >= 6:
            _add(signaux, "au moins 6 blocs <article> (grille de cartes)", categorie=2.0)
        pagine = ('next' in doc['rels'] or 'pagination' in doc['tokens']
                  or _RE_PAGE_N.search(doc['texte']))
        if pagine:
            _add(signaux, "pagination", categorie=2.0)

    if mots >= 1500:
        _add(signaux, f"contenu long ({mots} mots)", guide=1.5, article=1.0)
    elif mots >= 700:
        _add(signaux, f"contenu de fond ({mots} mots)", article=1.0, guide=0.5)

    etapes = sum(1 for entete in doc['entetes'] if _RE_ETAPE.search(entete))
    if etapes >= 3:
        _add(signaux, f"{etapes} intertitres numérotés en étapes", guide=2.0)

    if tags['form'] and tags['textarea'] and (champs['email'] or champs['tel']):
        _add(signaux, "formulaire de contact", landing_service=1.5)
    if doc['liens_nav'] and doc['liens_nav'] <= 5 and mots < 1200:
        _add(signaux, "navigation réduite (page de conversion)", landing_service=1.0)
    if re.search(r'add-to-cart|panier|woocommerce|shopify|snipcart', doc['tokens']):
        _add(signaux, "balisage de panier (WooCommerce, Shopify...)", fiche_produit=1.5)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _resoudre(scores):
    """Pick the winning type, using upstream's priority order to break ties."""
    notes = []
    meilleur = max(scores.values())
    if meilleur <= 0:
        notes.append(
            "Aucun signal de type détecté : retour au type par défaut de la taxonomie."
        )
        return 'article', notes
    candidats = [t for t in _PRIORITE if scores[t] >= meilleur - _MARGE_EGALITE]
    gagnant = candidats[0]
    if len(candidats) > 1:
        libelles = ', '.join(LIBELLES_TYPES[c] for c in candidats)
        notes.append(
            f"Scores serrés entre {libelles} : l'ordre de priorité de la taxonomie a tranché."
        )
    return gagnant, notes


def _confiance(scores, gagnant):
    premier = scores[gagnant]
    autres = sorted((v for t, v in scores.items() if t != gagnant), reverse=True)
    second = autres[0] if autres else 0.0
    if premier <= 0:
        return 0.15
    preuve = min(1.0, premier / _PLEINE_PREUVE)
    separation = (premier - second) / premier
    return round(max(0.15, min(0.95, 0.45 * preuve + 0.55 * separation)), 2)


def classify_page_type(html: str, url: str = '') -> dict:
    """Classify one page into the 9-type SXO taxonomy.

    Returns the winning `type`, a `confiance` between 0.15 and 0.95, the
    `signaux` that carried it, and the full `scores` table so a caller can show
    why a page was called something else than the author expected. Never raises:
    an unparseable page falls back to the taxonomy default (article) with low
    confidence, which is what the source prescribes.
    """
    doc = _parse_html(html or '')
    parsed = urlparse(url or '')
    segments = [s for s in (_plat(parsed.path or '')).split('/') if s]
    ctx = {
        'racine': not segments,
        'segments': segments,
        'hote': (parsed.netloc or '').lower(),
    }

    signaux = []
    _signaux_url(ctx, signaux)
    _signaux_schema(doc, ctx, signaux)
    _signaux_texte(doc, ctx, signaux)
    _signaux_structure(doc, ctx, signaux)

    scores = {t: 0.0 for t in TYPES_PAGE}
    for signal in signaux:
        for type_page, poids in signal['poids'].items():
            if type_page in scores:
                scores[type_page] += poids
    scores = {t: round(v, 2) for t, v in scores.items()}

    gagnant, notes = _resoudre(scores)
    retenus = sorted(
        (
            {'signal': s['signal'], 'poids': round(s['poids'][gagnant], 2)}
            for s in signaux if s['poids'].get(gagnant)
        ),
        key=lambda s: -s['poids'],
    )

    # Upstream's "Hybrid" type: educational depth and commercial intent on the
    # same page. Kept as a flag because the page still has one dominant shape.
    info = max(scores['article'], scores['guide'])
    commercial = max(scores['landing_service'], scores['fiche_produit'])
    faible, fort = min(info, commercial), max(info, commercial, 1.0)
    hybride = faible >= 2.5 and faible / fort >= 0.6
    if hybride:
        notes.append(
            "Page hybride : contenu éditorial et intention commerciale se disputent la page."
        )
    # A listing, a tool and a product sheet are legitimately text-light, so the
    # warning would be noise on those three. Anywhere else, an empty body means
    # the HTML we were handed is not what the reader sees.
    if doc['mots'] < 60 and gagnant not in ('categorie', 'outil', 'fiche_produit'):
        notes.append(
            "Moins de 60 mots lisibles extraits : page rendue en JavaScript ou HTML tronqué."
        )

    alternatives = [
        t for t, v in sorted(scores.items(), key=lambda kv: -kv[1])
        if t != gagnant and v > 0
    ][:3]

    return {
        'type': gagnant,
        'libelle': LIBELLES_TYPES[gagnant],
        'famille': FAMILLES_TYPES[gagnant],
        'confiance': _confiance(scores, gagnant),
        'signaux': retenus,
        'scores': scores,
        'alternatives': alternatives,
        'hybride': hybride,
        'mots': doc['mots'],
        'notes': notes,
    }


# ---------------------------------------------------------------------------
# Mismatch detection
# ---------------------------------------------------------------------------

_ALIAS_TYPES = {
    'accueil': 'accueil', 'home': 'accueil', 'homepage': 'accueil',
    'home page': 'accueil', 'page d accueil': 'accueil', 'racine': 'accueil',

    'article': 'article', 'articles': 'article', 'blog': 'article',
    'blog post': 'article', 'blogpost': 'article', 'blogue': 'article',
    'post': 'article', 'billet': 'article', 'news': 'article',
    'nouvelle': 'article', 'actualite': 'article', 'informational': 'article',
    'informationnel': 'article', 'editorial': 'article', 'magazine': 'article',

    'guide': 'guide', 'how to': 'guide', 'howto': 'guide', 'how-to': 'guide',
    'tutorial': 'guide', 'tutoriel': 'guide', 'tuto': 'guide',
    'guide pratique': 'guide', 'ressource': 'guide',

    'comparatif': 'comparatif', 'comparison': 'comparatif',
    'comparison page': 'comparatif', 'comparaison': 'comparatif',
    'versus': 'comparatif', 'vs': 'comparatif', 'listicle': 'comparatif',
    'alternative': 'comparatif', 'alternatives': 'comparatif',
    'review': 'comparatif', 'avis': 'comparatif', 'palmares': 'comparatif',

    'landing service': 'landing_service', 'landing': 'landing_service',
    'landing page': 'landing_service', 'service': 'landing_service',
    'service page': 'landing_service', 'page de service': 'landing_service',
    'hybrid': 'landing_service', 'hybride': 'landing_service',
    'saas': 'landing_service', 'commercial': 'landing_service',
    'transactional': 'landing_service', 'pricing': 'landing_service',
    'tarifs': 'landing_service',

    'fiche produit': 'fiche_produit', 'product': 'fiche_produit',
    'product page': 'fiche_produit', 'produit': 'fiche_produit',
    'ecommerce': 'fiche_produit', 'e-commerce': 'fiche_produit',
    'shopping': 'fiche_produit', 'boutique': 'fiche_produit',

    'categorie': 'categorie', 'category': 'categorie',
    'category page': 'categorie', 'collection': 'categorie',
    'listing': 'categorie', 'archive': 'categorie', 'archives': 'categorie',
    'tag': 'categorie', 'hub': 'categorie', 'index': 'categorie',

    'page locale': 'page_locale', 'local': 'page_locale',
    'local page': 'page_locale', 'local results': 'page_locale',
    'local pack': 'page_locale', 'gbp': 'page_locale', 'maps': 'page_locale',
    'annuaire': 'page_locale', 'directory': 'page_locale',

    'outil': 'outil', 'tool': 'outil', 'tool interactive': 'outil',
    'interactive': 'outil', 'calculator': 'outil', 'calculateur': 'outil',
    'generator': 'outil', 'generateur': 'outil', 'simulateur': 'outil',
}

# Upstream severity table (SKILL.md step 3) merged with the "Common mismatches"
# lines of page-type-taxonomy.md. Key: (type de la page, type dominant du SERP).
_TABLE_DESALIGNEMENT = {
    ('article', 'fiche_produit'): ('critique', (
        "Le top 10 est fait de fiches produit. Un article ne percera pas : crée une "
        "vraie fiche produit (prix, disponibilité, schema Product, bouton d'achat) et "
        "garde l'article comme contenu de support qui pointe vers elle."
    )),
    ('article', 'comparatif'): ('elevee', (
        "Restructure la page en comparatif : tableau de critères, avantages et "
        "inconvénients par option, et un verdict « meilleur pour X »."
    )),
    ('article', 'landing_service'): ('critique', (
        "La requête appelle une page qui vend. Crée une landing de service avec un CTA "
        "de soumission, tes preuves (réalisations, témoignages) et tes forfaits."
    )),
    ('article', 'page_locale'): ('critique', (
        "La requête est locale. Crée une page ville avec NAP complet, schema "
        "LocalBusiness, carte, zone desservie et la ville dans le H1 et le titre."
    )),
    ('article', 'outil'): ('critique', (
        "Les gens veulent FAIRE, pas lire. Construis l'outil (calculateur, "
        "vérificateur) au-dessus de la ligne de flottaison et garde le texte dessous."
    )),
    ('article', 'accueil'): ('moyenne', (
        "Le top 10 est occupé par des pages d'accueil de marques : requête de marque ou "
        "de navigation. Vise plutôt une requête descriptive où un article a sa place."
    )),
    ('guide', 'fiche_produit'): ('critique', (
        "Le top 10 vend un produit. Un guide ne remplacera pas une fiche produit : crée "
        "la fiche et relie le guide dessus."
    )),
    ('guide', 'comparatif'): ('elevee', (
        "Transforme le guide en comparatif : matrice de critères, verdict par profil, "
        "et garde les explications en second niveau."
    )),
    ('guide', 'outil'): ('critique', (
        "Google récompense un outil, pas des explications. Livre le calcul ou la "
        "vérification directement sur la page."
    )),
    ('guide', 'page_locale'): ('critique', (
        "Requête locale : il faut une page ancrée sur la ville (NAP, LocalBusiness, "
        "carte), pas un guide générique."
    )),
    ('guide', 'landing_service'): ('critique', (
        "La requête est commerciale. Crée une landing de service et réoriente le guide "
        "vers une requête informationnelle."
    )),
    ('fiche_produit', 'article'): ('elevee', (
        "Ajoute une couche éditoriale : cas d'usage, comparaisons, questions fréquentes, "
        "guide d'achat. La fiche seule ne répond pas à une requête informationnelle."
    )),
    ('fiche_produit', 'guide'): ('elevee', (
        "La requête demande une explication. Ajoute un guide d'achat complet sur la page "
        "ou crée un guide dédié qui pointe vers la fiche."
    )),
    ('fiche_produit', 'comparatif'): ('elevee', (
        "L'internaute compare avant d'acheter. Crée un comparatif de tes modèles ou de "
        "tes concurrents plutôt que d'exposer une seule fiche."
    )),
    ('fiche_produit', 'landing_service'): ('moyenne', (
        "La requête vise un service sur mesure, pas un article en stock. Reformule la "
        "page en offre de service avec processus et soumission."
    )),
    ('comparatif', 'fiche_produit'): ('moyenne', (
        "L'intention est d'acheter, pas de comparer. Rends l'achat possible depuis la "
        "page ou crée une fiche produit dédiée."
    )),
    ('landing_service', 'outil'): ('elevee', (
        "Le top 10 est fait d'outils. Ajoute un outil fonctionnel (calculateur, "
        "estimateur) au-dessus de la ligne de flottaison au lieu de le promettre."
    )),
    ('landing_service', 'page_locale'): ('moyenne', (
        "Ajoute les signaux locaux à la page de service : NAP, schema LocalBusiness, "
        "ville dans le titre et le H1, carte, secteurs desservis."
    )),
    ('landing_service', 'article'): ('critique', (
        "La requête est informationnelle. Une landing ne répond pas à un « comment » : "
        "publie un article ou un guide et garde la landing pour la requête commerciale."
    )),
    ('landing_service', 'guide'): ('critique', (
        "La requête demande un mode d'emploi. Publie le guide et laisse la landing "
        "cibler la requête d'achat."
    )),
    ('landing_service', 'comparatif'): ('elevee', (
        "L'internaute magasine. Publie un comparatif honnête (toi inclus) plutôt "
        "qu'une page de vente."
    )),
    ('landing_service', 'fiche_produit'): ('moyenne', (
        "Le top 10 vend un produit défini. Expose un produit avec prix et "
        "disponibilité plutôt qu'une offre de service floue."
    )),
    ('page_locale', 'article'): ('elevee', (
        "La requête cherche de l'information, pas un commerce. Publie le contenu "
        "éditorial correspondant et garde la page locale sur les requêtes « ville »."
    )),
    ('outil', 'article'): ('moyenne', (
        "Le top 10 explique avant d'agir. Ajoute un vrai contenu de fond sous l'outil "
        "(méthode, exemples, questions fréquentes)."
    )),
    ('accueil', 'article'): ('elevee', (
        "Ta page d'accueil se bat sur une requête informationnelle. Crée une page "
        "dédiée : l'accueil doit rester sur ta requête de marque."
    )),
    ('accueil', 'guide'): ('elevee', (
        "Crée un guide dédié. L'accueil ne peut pas être optimisée pour une requête "
        "précise sans nuire au reste."
    )),
    ('accueil', 'fiche_produit'): ('elevee', (
        "Crée une fiche produit dédiée et laisse l'accueil sur la marque."
    )),
    ('accueil', 'page_locale'): ('elevee', (
        "Crée une page par ville. L'accueil ne peut pas porter tous les marchés."
    )),
    ('categorie', 'article'): ('moyenne', (
        "Une page de listing ne répond pas à la question. Publie un article et laisse la "
        "catégorie faire le maillage."
    )),
    ('categorie', 'guide'): ('moyenne', (
        "Publie un guide dédié : une liste de liens ne satisfait pas cette requête."
    )),
    ('categorie', 'fiche_produit'): ('moyenne', (
        "La requête vise un produit précis. Fais remonter la fiche plutôt que la "
        "catégorie."
    )),
}


def normalize_page_type(valeur) -> str:
    """Map any spelling of a page type to a taxonomy key. '' when unknown.

    Accepts upstream's English labels ("Blog Post", "Tool / Interactive") as
    well as Gridar's French keys, because SERP classifications reach this
    function from a Claude call whose wording is not guaranteed.
    """
    plat = _plat(valeur)
    if not plat:
        return ''
    plat = re.sub(r"[\\/_,;:.+&]", ' ', plat)
    plat = plat.replace("'", ' ')
    plat = ' '.join(plat.split())
    if plat in _ALIAS_TYPES:
        return _ALIAS_TYPES[plat]
    sans_page = re.sub(r'\b(page|pages|type|resultat|resultats|de|du|d)\b', ' ', plat)
    sans_page = ' '.join(sans_page.split())
    if sans_page in _ALIAS_TYPES:
        return _ALIAS_TYPES[sans_page]
    for mot in sans_page.split():
        if mot in _ALIAS_TYPES:
            return _ALIAS_TYPES[mot]
    return ''


def _descendre(severite, crans=1):
    index = _SEVERITES.index(severite)
    return _SEVERITES[max(0, index - crans)]


def detect_mismatch(page_type: str, serp_types: list[str]) -> dict:
    """Compare a page type against the dominant type of the top 10.

    Consensus thresholds come from the source: above 60% the SERP has decided,
    40 to 60% it is mixed, below 40% it is fragmented and the mismatch stops
    being a wall. Two dampeners were added on top of upstream's flat severity
    table, because a raw table over-alarms: a mixed SERP drops the severity one
    notch, and so does a SERP where the page's own type already holds at least
    20% of the results. If your type ranks, the type is not what blocks you.
    """
    type_page = normalize_page_type(page_type)
    repartition = Counter()
    for brut in (serp_types or []):
        repartition[normalize_page_type(brut) or 'inconnu'] += 1
    echantillon = sum(repartition.values())
    connus = {t: n for t, n in repartition.items() if t != 'inconnu'}

    base = {
        'verdict': 'indetermine',
        'severite': 'aucune',
        'type_page': type_page,
        'libelle_page': LIBELLES_TYPES.get(type_page, 'Inconnu'),
        'type_dominant': None,
        'libelle_dominant': None,
        'consensus': 0.0,
        'force_consensus': None,
        'part_de_mon_type': 0.0,
        'repartition': dict(repartition),
        'echantillon': echantillon,
        'fiabilite': 'faible',
        'recommandation': '',
        'explication': '',
        'notes': [],
    }

    if not type_page:
        base['recommandation'] = (
            "Type de page inconnu : passe le résultat de classify_page_type ou un des "
            "libellés de la taxonomie."
        )
        base['explication'] = f"Type reçu non reconnu : {page_type!r}."
        return base
    if not connus:
        base['recommandation'] = (
            "Aucun type exploitable dans le top 10 : relance l'analyse de SERP avant de "
            "conclure quoi que ce soit sur ta page."
        )
        base['explication'] = (
            "Aucun des types de SERP fournis n'a pu être rattaché à la taxonomie."
            if echantillon else "Aucun résultat de SERP fourni."
        )
        return base

    # Ties on count are broken by the taxonomy priority so the verdict is stable.
    dominant = min(
        connus, key=lambda t: (-connus[t], _PRIORITE.index(t) if t in _PRIORITE else 99),
    )
    consensus = connus[dominant] / echantillon
    part_mienne = repartition.get(type_page, 0) / echantillon
    if consensus >= 0.6:
        force = 'fort'
    elif consensus >= 0.4:
        force = 'mixte'
    else:
        force = 'fragmente'

    notes = []
    fiabilite = 'bonne'
    if echantillon < 5:
        fiabilite = 'faible'
        notes.append(
            f"Échantillon de {echantillon} résultat(s) seulement : verdict indicatif."
        )
    if repartition.get('inconnu'):
        notes.append(
            f"{repartition['inconnu']} résultat(s) non classés, exclus du calcul du type dominant."
        )

    base.update({
        'type_dominant': dominant,
        'libelle_dominant': LIBELLES_TYPES[dominant],
        'consensus': round(consensus, 2),
        'force_consensus': force,
        'part_de_mon_type': round(part_mienne, 2),
        'fiabilite': fiabilite,
    })
    pct = round(consensus * 100)
    detail = (
        f"{connus[dominant]}/{echantillon} résultats du top 10 sont des pages de type "
        f"« {LIBELLES_TYPES[dominant]} » (consensus {force} à {pct} %). "
        f"Ta page est de type « {LIBELLES_TYPES[type_page]} »."
    )

    if type_page == dominant:
        base.update({
            'verdict': 'aligne',
            'severite': 'aucune',
            'recommandation': (
                "Type aligné avec la SERP. Le blocage est ailleurs : profondeur du "
                "contenu, UX, autorité ou fraîcheur."
            ),
            'explication': detail,
            'notes': notes,
        })
        return base

    if force == 'fragmente':
        base.update({
            'verdict': 'serp_fragmente',
            'severite': 'faible' if part_mienne else 'moyenne',
            'recommandation': (
                "SERP fragmentée : aucun type ne dépasse 40 %, donc pas de mur de format. "
                "Joue la différenciation (profondeur, angle, format riche) plutôt qu'un "
                "changement de type."
                + ("" if part_mienne else
                   f" Note quand même qu'aucune page de type « {LIBELLES_TYPES[type_page]} » "
                   "n'apparaît dans le top 10.")
            ),
            'explication': detail,
            'notes': notes,
        })
        return base

    severite, recommandation = _TABLE_DESALIGNEMENT.get((type_page, dominant), (None, None))
    if severite is None:
        if FAMILLES_TYPES[type_page] == FAMILLES_TYPES[dominant]:
            severite = 'faible'
            recommandation = (
                f"Même famille d'intention, format différent : rapproche la page du format "
                f"« {LIBELLES_TYPES[dominant]} » (structure, titre, éléments attendus) sans "
                "repartir de zéro."
            )
        else:
            severite = 'moyenne'
            recommandation = (
                f"Le top 10 attend des pages « {LIBELLES_TYPES[dominant]} ». Convertis la "
                f"page vers ce format ou crée une page dédiée de ce type, et repositionne "
                "celle-ci sur une requête qui correspond à sa forme."
            )

    if force == 'mixte':
        severite = _descendre(severite)
        notes.append(
            "Consensus mixte (entre 40 et 60 %) : sévérité abaissée d'un cran."
        )
    if part_mienne >= 0.2:
        severite = _descendre(severite)
        notes.append(
            f"Ton type occupe déjà {round(part_mienne * 100)} % du top 10 : le type n'est "
            "pas un mur, sévérité abaissée d'un cran."
        )
    if severite == 'aucune':
        severite = 'faible'

    base.update({
        'verdict': 'desalignement' if severite in ('moyenne', 'elevee', 'critique')
                   else 'desalignement_leger',
        'severite': severite,
        'recommandation': recommandation,
        'explication': detail,
        'notes': notes,
    })
    return base
