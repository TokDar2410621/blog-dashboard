"""Local SEO grid and NAP consistency for a Quebec small business.

Ported from claude-seo v2.2.4 `skills/seo-local/SKILL.md` and
`skills/seo-maps/SKILL.md`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream ships six weighted dimensions as prose and leaves NAP extraction to an
LLM reading the page; both become deterministic functions here. The reader had
to be rewritten for Quebec: the address grammar is French ("1234, boul. Talbot,
app. 5"), the postal code is Canadian and the phone shapes are the ones a
Saguenay footer really uses. Comparison normalizes before it compares, because
a site writing "boulevard" and a Google listing writing "boul." hold the same
address and flagging them burns the client's attention on nothing. Scoring
keeps the source's 25/20/20/15/10/10 but adds per-check applicability: what
cannot be read leaves the denominator instead of scoring zero.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from html.parser import HTMLParser

from .html_parse import extract_seo_signals

__all__ = [
    'DIMENSIONS',
    'VERTICALES',
    'SEVERITES',
    'extract_nap',
    'compare_nap',
    'score_local_seo',
    'detect_vertical',
]


# Ordered from harmless to blocking, same vocabulary as `sxo.detect_mismatch`
# so a dashboard can sort findings from both modules in one list.
SEVERITES = ('aucune', 'faible', 'moyenne', 'elevee', 'critique')

# Source weights are upstream's (seo-local, "Analysis Dimensions").
DIMENSIONS = (
    ('fiche_google', 'Fiche Google', 25),
    ('avis', 'Avis et réputation', 20),
    ('seo_local_page', 'SEO local sur la page', 20),
    ('nap_citations', 'Cohérence NAP et citations', 15),
    ('schema_local', 'Balisage LocalBusiness', 10),
    ('autorite_locale', 'Autorité locale', 10),
)

# Six trades, each with the words a Quebec page of that trade really writes.
# `forts` are terms nobody outside the trade uses, so one of them decides;
# `faibles` are supporting vocabulary that only nudges, and their contribution
# is capped so a page repeating "produits" thirty times cannot outrank a single
# "changement d'huile". Every term is written without accents and in lowercase
# because matching runs on the `_plat` form of the page.
VERTICALES = (
    ('restauration', 'Restauration', 'Restaurant',
     ("menu du jour", "table d'hote", "notre menu", "carte des vins",
      "reserver une table", "reservation de table", "apportez votre vin",
      "plat principal", "menu enfant", "pour emporter", "livraison de repas",
      "brunch", "poutine", "pizzeria", "rotisserie", "casse-croute", "bistro",
      "traiteur", "salle a manger", "chef cuisinier", "creme glacee"),
     ("restaurant", "repas", "cuisine", "dessert", "terrasse", "dejeuner",
      "diner", "souper", "boisson", "cafe", "bar", "menu")),
    ('sante', 'Santé', 'MedicalBusiness',
     ("clinique dentaire", "clinique medicale", "physiotherapie",
      "chiropratique", "chiropraticien", "denturologiste", "orthodontie",
      "optometriste", "podiatre", "osteopathie", "massotherapie", "psychologue",
      "ergotherapie", "acupuncture", "soins dentaires", "examen de la vue",
      "nettoyage dentaire", "couronne dentaire", "carte soleil",
      "hygieniste dentaire", "orthese"),
     ("clinique", "patient", "traitement", "consultation", "sante", "douleur",
      "therapie", "diagnostic", "ordonnance", "soins", "rendez-vous")),
    ('construction', 'Construction et rénovation', 'HomeAndConstructionBusiness',
     ("entrepreneur general", "licence rbq", "rbq", "toiture", "couvreur",
      "plomberie", "plombier", "electricien", "excavation", "charpente",
      "coffrage", "fondation", "gypse", "ebenisterie", "armoires de cuisine",
      "pose de plancher", "revetement exterieur", "salle de bain cle en main",
      "renovation", "thermopompe", "deneigement de toiture", "beton"),
     ("construction", "travaux", "chantier", "installation", "reparation",
      "soumission", "estimation", "materiaux", "residentiel", "commercial",
      "garantie")),
    ('services_professionnels', 'Services professionnels', 'ProfessionalService',
     ("comptable", "cpa", "notaire", "avocat", "fiscaliste", "tenue de livres",
      "declaration de revenus", "impot des particuliers", "droit familial",
      "droit du travail", "consultation juridique", "planification financiere",
      "courtier immobilier", "courtier hypothecaire", "assurance vie",
      "conseiller financier", "etats financiers", "incorporation",
      "mediation familiale", "agence de marketing"),
     ("cabinet", "honoraires", "mandat", "conseil", "expertise", "strategie",
      "gestion", "dossier", "accompagnement", "consultation")),
    ('commerce_detail', 'Commerce de détail', 'Store',
     ("boutique en ligne", "ajouter au panier", "notre boutique", "en stock",
      "livraison gratuite", "magasinez", "magasiner", "nos produits",
      "catalogue", "succursale", "quincaillerie", "epicerie", "friperie",
      "pharmacie", "fleuriste", "librairie", "animalerie", "en magasin",
      "essayage", "carte-cadeau"),
     ("magasin", "boutique", "produit", "prix", "marque", "inventaire",
      "achat", "vente", "commande", "rabais", "solde")),
    ('automobile', 'Automobile', 'AutomotiveBusiness',
     ("garage automobile", "mecanique automobile", "changement d'huile",
      "pneus d'hiver", "pose de pneus", "concessionnaire",
      "vehicule d'occasion", "voiture usagee", "carrosserie", "debosselage",
      "antirouille", "inspection mecanique", "silencieux", "remorquage",
      "esthetique automobile", "alignement des roues", "saaq",
      "freins et suspension", "entreposage de pneus"),
     ("automobile", "vehicule", "voiture", "auto", "pneu", "moteur", "garage",
      "entretien", "kilometrage", "essai routier")),
)

_MAX_HTML = 3_000_000
_MAX_CANDIDATS = 12

# Where a finding came from, and how much it is trusted. A number in JSON-LD is
# what Google reads; a number floating in body text could be a supplier's.
_SOURCES = {
    'jsonld': ('JSON-LD', 0),
    'microdata': ('Microdonnées', 1),
    'balise_address': ('Balise <address>', 2),
    'lien_tel': ('Lien tel:', 2),
    'pied_de_page': ('Pied de page', 3),
    'meta_og': ('Métadonnée og:site_name', 4),
    'titre': ('Titre de la page', 5),
    'texte': ('Texte de la page', 6),
}


def _plat(valeur) -> str:
    """Lowercase, accent-free, whitespace-collapsed form used by the matchers.

    Quebec pages mix "Montréal" and "Montreal" inside the same footer, and CMS
    exports mangle apostrophes, so every text rule runs on this form.
    """
    if not valeur:
        return ''
    texte = str(valeur)
    for code in (0x2018, 0x2019, 0x201A, 0x201B, 0x02BC, 0x2032):
        texte = texte.replace(chr(code), "'")
    texte = texte.replace('œ', 'oe').replace('Œ', 'OE')
    texte = texte.replace('æ', 'ae').replace('Æ', 'AE')
    texte = unicodedata.normalize('NFD', texte)
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return ' '.join(texte.lower().split())


# ---------------------------------------------------------------------------
# Quebec formats: phone, postal code, province, city, street
# ---------------------------------------------------------------------------

# NANP shape with every separator a Quebec site uses, plus the extension words.
# The area code and the exchange both have to start at 2 or higher, which is
# what keeps a year or a price out of the results.
_RE_TEL = re.compile(
    r"(?<![\w-])(?:\+?1[\s.\-]?)?"
    r"(?:\((?P<ind1>[2-9]\d{2})\)|(?P<ind2>[2-9]\d{2}))"
    r"[\s.\-]?(?P<pre>[2-9]\d{2})[\s.\-]?(?P<lig>\d{4})"
    r"(?:\s*(?:poste|pos\.|ext\.?|extension|#)\s*(?P<poste>\d{1,6}))?"
    r"(?!\d)",
    re.IGNORECASE,
)

# Canada Post never issues D, F, I, O, Q or U, and W and Z never open a code.
_RE_CODE_POSTAL = re.compile(
    r"\b([ABCEGHJKLMNPRSTVXY]\d[ABCEGHJKLMNPRSTVWXYZ])[ -]?"
    r"(\d[ABCEGHJKLMNPRSTVWXYZ]\d)\b",
    re.IGNORECASE,
)

# Codes stay case-sensitive: with IGNORECASE, Ontario's "ON" would match the
# French pronoun "on" in every second sentence.
_RE_PROVINCE_CODE = re.compile(r"\b(QC|PQ|ON|NB|NS|PE|NL|MB|SK|AB|BC|CB|YT|NT|NU)\b")
_RE_PROVINCE_NOM = re.compile(
    r"\b(qu[ée]bec|ontario|nouveau[- ]brunswick|nouvelle[- ][ée]cosse|"
    r"[îi]le[- ]du[- ]prince[- ][ée]douard|terre[- ]neuve|manitoba|saskatchewan|"
    r"alberta|colombie[- ]britannique|yukon|nunavut)\b",
    re.IGNORECASE,
)

_PROVINCES = {
    'qc': 'QC', 'pq': 'QC', 'quebec': 'QC',
    'on': 'ON', 'ontario': 'ON',
    'nb': 'NB', 'nouveau-brunswick': 'NB', 'nouveau brunswick': 'NB',
    'ns': 'NS', 'nouvelle-ecosse': 'NS', 'nouvelle ecosse': 'NS',
    'pe': 'PE', 'ile-du-prince-edouard': 'PE',
    'nl': 'NL', 'terre-neuve': 'NL', 'terre neuve': 'NL',
    'mb': 'MB', 'manitoba': 'MB',
    'sk': 'SK', 'saskatchewan': 'SK',
    'ab': 'AB', 'alberta': 'AB',
    'bc': 'BC', 'cb': 'BC', 'colombie-britannique': 'BC',
    'yt': 'YT', 'yukon': 'YT',
    'nt': 'NT', 'nu': 'NU', 'nunavut': 'NU',
}

# Municipalities, boroughs and the sectors that still name themselves on
# letterhead (Chicoutimi and Jonquiere merged into Saguenay in 2002 and every
# local business still writes the old name).
_VILLES_QC = (
    'montreal', 'quebec', 'laval', 'gatineau', 'longueuil', 'sherbrooke',
    'saguenay', 'chicoutimi', 'jonquiere', 'la baie', 'arvida', 'kenogami',
    'levis', 'trois-rivieres', 'terrebonne', 'saint-jean-sur-richelieu',
    'repentigny', 'brossard', 'drummondville', 'saint-jerome', 'granby',
    'blainville', 'saint-hyacinthe', 'shawinigan', 'dollard-des-ormeaux',
    'rimouski', 'chateauguay', 'victoriaville', 'rouyn-noranda', 'sorel-tracy',
    'val-d\'or', 'sept-iles', 'boucherville', 'mirabel', 'salaberry-de-valleyfield',
    'mascouche', 'saint-eustache', 'joliette', 'alma', 'sainte-julie',
    'vaudreuil-dorion', 'beloeil', 'magog', 'baie-comeau', 'thetford mines',
    'dorval', 'pointe-claire', 'westmount', 'lasalle', 'verdun', 'anjou',
    'lachine', 'outremont', 'rosemont', 'ahuntsic', 'hochelaga', 'plateau',
    'sainte-foy', 'beauport', 'charlesbourg', 'limoilou', 'lebourgneuf',
    'gaspe', 'matane', 'amos', 'roberval', 'dolbeau-mistassini', 'saint-felicien',
    'sainte-therese', 'candiac', 'la prairie', 'varennes', 'contrecoeur',
    'ottawa', 'toronto', 'hawkesbury', 'cornwall',
)
_RE_VILLE = re.compile(
    r"\b(?:" + '|'.join(re.escape(v) for v in _VILLES_QC) + r")\b"
)

# Regions and administrative areas, used for the local-intent checks where the
# business sells to a territory rather than to a single city.
_REGIONS_QC = (
    'rive-sud', 'rive-nord', 'monteregie', 'lanaudiere', 'laurentides',
    'outaouais', 'estrie', 'mauricie', 'abitibi', 'abitibi-temiscamingue',
    'gaspesie', 'charlevoix', 'bas-saint-laurent', 'cote-nord', 'lac-saint-jean',
    'saguenay-lac-saint-jean', 'centre-du-quebec', 'chaudiere-appalaches',
    'capitale-nationale', 'grand montreal', 'couronne nord', 'couronne sud',
    'nord-du-quebec', 'iles-de-la-madeleine', 'beauce', 'temiscamingue',
)
_RE_REGION = re.compile(
    r"\b(?:" + '|'.join(re.escape(r) for r in _REGIONS_QC) + r")\b"
)

# Street generics, longest spelling first so `avenue` is not eaten by `av`.
# The short English forms (st., rd., dr.) are deliberately absent: on a French
# page "St-Jean" and "Dr. Tremblay" would each look like a street.
_VOIE = (
    r"(?:boulevard|boul\.?|blvd\.?|bd\.?|avenue|ave\.?|av\.?|chemin|ch\.?|"
    r"autoroute|route|rte\.?|rang|mont[ée]e|c[oô]te|croissant|terrasse|"
    r"promenade|esplanade|impasse|all[ée]e|ruelle|sentier|passage|carr[ée]|"
    r"place|quai|rue|street|road|drive|lane|court|crescent|way)"
)

# A civic number, up to two filler tokens ("3e ", "de la "), then the generic.
# Quebec writes both "1234, boul. Talbot" and "1234, 3e Avenue", so the generic
# cannot be pinned to a fixed position after the number.
_RE_CIVIQUE = re.compile(
    r"(?<![\w-])(?P<numero>\d{1,5}[A-Za-z]?(?:\s?-\s?\d{1,5}[A-Za-z]?)?)"
    r"\s*,?\s+(?P<avant>(?:[^\s,;|]+\s+){0,2}?)"
    r"(?P<voie>" + _VOIE + r")\b",
    re.IGNORECASE,
)

# Where an address line stops and the rest of the footer begins.
_RE_STOP_ADRESSE = re.compile(
    r"\s*(?:\||•|·|●|»|T[ée]l[ée]phone|T[ée]l\.?\s*:|Tel\b|Fax|Courriel|"
    r"Email|Sans frais|Ouvert|Horaire|Heures)",
    re.IGNORECASE,
)

_RE_UNITE = re.compile(
    r"\b(?:appartement|appart\.?|app\.?|apt\.?|bureau|bur\.?|suite|local|"
    r"unit[ée]|porte)\s*[:.]?\s*(?P<unite>[\w-]{1,10})",
    re.IGNORECASE,
)

# French and English ordinals, folded to the bare digit so "3e Avenue" and
# "3ième Avenue" compare equal.
_RE_ORDINAL = re.compile(r"\b(\d+)\s*(?:ers?|res?|i?[eè]mes?|es?|st|nd|rd|th)\b")

# Street abbreviations expanded before comparison. Without this every listing
# that writes "boul." looks inconsistent with the site that writes "boulevard".
_ABREVIATIONS_VOIE = {
    'boul': 'boulevard', 'boulv': 'boulevard', 'blvd': 'boulevard',
    'bd': 'boulevard', 'av': 'avenue', 'ave': 'avenue', 'aven': 'avenue',
    'ch': 'chemin', 'rte': 'route', 'mtee': 'montee', 'pl': 'place',
    'crois': 'croissant', 'terr': 'terrasse', 'st': 'saint', 'ste': 'sainte',
    'sts': 'saints', 'stes': 'saintes', 'e': 'est', 'o': 'ouest',
    'w': 'ouest', 'n': 'nord', 's': 'sud', 'app': 'app', 'appt': 'app',
    'apt': 'app', 'appart': 'app', 'appartement': 'app', 'bur': 'app',
    'bureau': 'app', 'suite': 'app', 'local': 'app', 'unite': 'app',
    'porte': 'app', 'no': '', 'num': '',
}

# Legal forms dropped before two business names are compared.
_RE_FORME_JURIDIQUE = re.compile(
    r"\b(?:inc|ltee|ltd|limitee|limited|enr|senc|sencrl|srl|s\s?e\s?n\s?c|"
    r"cie|co|corp|corporation|sa|sarl|llc|llp|plc|gmbh|reg|division|div|"
    r"et fils|and sons|group[e]?|holdings?)\b"
)


# ---------------------------------------------------------------------------
# HTML reading: the regions where a NAP hides
# ---------------------------------------------------------------------------

_TAGS_VIDES = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
})

_TAGS_IGNORES = frozenset({
    'script', 'style', 'noscript', 'template', 'svg', 'canvas', 'select',
})

_TAGS_BLOCS = frozenset({
    'address', 'article', 'aside', 'blockquote', 'br', 'dd', 'div', 'dl', 'dt',
    'fieldset', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'section',
    'table', 'td', 'th', 'tr', 'ul',
})

_ITEMPROPS = frozenset({
    'name', 'legalname', 'streetaddress', 'addresslocality', 'addressregion',
    'postalcode', 'addresscountry', 'telephone', 'faxnumber',
})

_RE_ZONE_PIED = re.compile(r"footer|pied[-_ ]?de[-_ ]?page|\bpied\b|coordonnees")

_RE_CARTE = re.compile(
    r"google\.[a-z.]+/maps|maps\.google|google\.com/maps/embed|"
    r"openstreetmap\.org|mapbox\.com|bing\.com/maps|apple\.com/maps"
)
_RE_FICHE_ID = re.compile(
    r"place_id=|placeid=|[?&]cid=|maps\.app\.goo\.gl|g\.page/|"
    r"goo\.gl/maps|maps/place/"
)


class _Cadre:
    """One open element: the flags it propagates and the text it captures."""

    __slots__ = ('tag', 'skip', 'pied', 'adresse', 'itemprop', 'buf')

    def __init__(self, tag, skip, pied, adresse, itemprop=None):
        self.tag = tag
        self.skip = skip
        self.pied = pied
        self.adresse = adresse
        self.itemprop = itemprop
        self.buf = [] if itemprop else None


class _ScanNap(HTMLParser):
    """Collect footer text, <address> blocks, microdata and contact links.

    `html_parse.extract_seo_signals` deliberately drops `nav` and `footer` from
    its visible text, and a Quebec NAP lives in the footer nine times out of
    ten, so this second pass exists to read exactly what the other one throws
    away. It also keeps `tel:` hrefs, which the shared parser drops so they do
    not inflate the external-link count of every local page.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.pied_parts: list[str] = []
        self.adresse_parts: list[str] = []
        self.microdata: dict[str, str] = {}
        self.tel_hrefs: list[str] = []
        self.hrefs: list[str] = []
        self.iframes: list[str] = []
        self.itemtypes: list[str] = []
        self.formulaire = False
        self._stack: list[_Cadre] = []
        self._captures: list[_Cadre] = []

    # -- state helpers -----------------------------------------------------

    def _dessus(self):
        return self._stack[-1] if self._stack else None

    def _emettre(self, texte, cadre):
        if not cadre or not cadre.skip:
            if len(self.parts) < 60000:
                self.parts.append(texte)
            if cadre and cadre.pied and len(self.pied_parts) < 20000:
                self.pied_parts.append(texte)
            if cadre and cadre.adresse and len(self.adresse_parts) < 5000:
                self.adresse_parts.append(texte)

    # -- HTMLParser hooks --------------------------------------------------

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = {}
        for cle, valeur in attrs:
            cle = cle.lower()
            if cle not in a:
                a[cle] = valeur or ''

        parent = self._dessus()
        if tag in _TAGS_BLOCS:
            self._emettre('\n', parent)

        href = (a.get('href') or '').strip()
        if href:
            if href.lower().startswith('tel:'):
                self.tel_hrefs.append(href[4:])
            elif len(self.hrefs) < 3000:
                self.hrefs.append(href)
        if tag == 'iframe':
            self.iframes.append((a.get('src') or '').lower())
        if tag == 'form':
            self.formulaire = True
        itemtype = (a.get('itemtype') or '').rstrip('/')
        if itemtype:
            self.itemtypes.append(itemtype.rsplit('/', 1)[-1].lower())

        itemprop = (a.get('itemprop') or '').strip().lower()
        if itemprop and itemprop in _ITEMPROPS and a.get('content'):
            self.microdata.setdefault(itemprop, a['content'].strip())
            itemprop = ''
        if itemprop not in _ITEMPROPS:
            itemprop = ''

        if tag in _TAGS_VIDES:
            return

        marqueurs = (a.get('class', '') + ' ' + a.get('id', '')).lower()
        cadre = _Cadre(
            tag,
            skip=bool(parent and parent.skip) or tag in _TAGS_IGNORES,
            pied=bool(parent and parent.pied) or tag == 'footer'
                 or bool(marqueurs and _RE_ZONE_PIED.search(marqueurs)),
            adresse=bool(parent and parent.adresse) or tag == 'address',
            itemprop=itemprop or None,
        )
        self._stack.append(cadre)
        if cadre.itemprop:
            self._captures.append(cadre)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _TAGS_VIDES:
            return
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                for cadre in reversed(self._stack[i:]):
                    self._vider(cadre)
                del self._stack[i:]
                break
        if tag in _TAGS_BLOCS:
            self._emettre('\n', self._dessus())

    def handle_data(self, data):
        if not data:
            return
        cadre = self._dessus()
        for capture in self._captures:
            capture.buf.append(data)
        self._emettre(data, cadre)

    def finish(self):
        for cadre in reversed(self._stack):
            self._vider(cadre)
        self._stack = []
        self._captures = []
        return self

    def _vider(self, cadre):
        if cadre.buf is None:
            return
        texte = ' '.join(''.join(cadre.buf).split())
        cadre.buf = None
        if cadre in self._captures:
            self._captures.remove(cadre)
        if texte:
            self.microdata.setdefault(cadre.itemprop, texte)


def _scan(html: str) -> _ScanNap:
    parser = _ScanNap()
    try:
        parser.feed((html or '')[:_MAX_HTML])
        parser.close()
    except Exception:
        # Audited sites ship broken markup constantly. Keep what was read
        # before the break rather than losing the whole page.
        pass
    return parser.finish()


def _lignes(parts) -> list[str]:
    """Flatten collected text into non-empty single-space lines."""
    brut = ''.join(parts)
    sorties = []
    for ligne in brut.split('\n'):
        ligne = ' '.join(ligne.split())
        if ligne:
            sorties.append(ligne)
    return sorties


# ---------------------------------------------------------------------------
# Reading one line: address, phone, business name
# ---------------------------------------------------------------------------

_RE_MOT = re.compile(r'\S+')

# Separators a page title puts between the topic and the brand. Written as
# codepoints because this repository bans the characters themselves from its
# source, while a Quebec title uses them constantly.
_SEPARATEURS_TITRE = tuple(chr(code) for code in (
    0x007C, 0x2010, 0x2012, 0x2013, 0x2014, 0x2015, 0x2022, 0x00B7, 0x2043,
))
_RE_SEPARATEUR_TITRE = re.compile(
    '|'.join(re.escape(caractere) for caractere in _SEPARATEURS_TITRE)
    + r'|\s+-\s+'
)

# The year range is read as "four digits, up to three characters, four digits"
# so no dash has to be spelled out here.
_RE_COPYRIGHT = re.compile(
    r"(?:©|\(c\)|copyright)\s*(?:\d{4}(?:\D{0,3}\d{4})?)?[\s.,:]*(?P<nom>[^|,;.]{2,60})",
    re.IGNORECASE,
)

# Lines that look like a name but are not one.
_RE_NON_NOM = re.compile(
    r"^(?:tous droits|all rights|politique|conditions|mentions|plan du site|"
    r"con[cç]u par|realisation|propuls[ée]|powered by|site web par)"
)

# schema.org LocalBusiness and the subtypes a Quebec small business really
# declares. Organization is absent on purpose: it is not a local entity, and
# scoring it as one would let a national brand page pass the local check.
_TYPES_LOCAUX = frozenset({
    'localbusiness', 'restaurant', 'foodestablishment', 'bakery', 'barorpub',
    'brewery', 'cafeorcoffeeshop', 'fastfoodrestaurant', 'icecreamshop',
    'winery', 'distillery', 'store', 'autopartsstore', 'bikestore',
    'bookstore', 'clothingstore', 'computerstore', 'conveniencestore',
    'departmentstore', 'electronicsstore', 'florist', 'furniturestore',
    'gardenstore', 'grocerystore', 'hardwarestore', 'homegoodsstore',
    'jewelrystore', 'liquorstore', 'mobilephonestore', 'musicstore',
    'officeequipmentstore', 'outletstore', 'pawnshop', 'petstore',
    'shoestore', 'sportinggoodsstore', 'tirestore', 'toystore',
    'wholesalestore', 'medicalbusiness', 'medicalclinic', 'dentist',
    'physician', 'optician', 'pharmacy', 'veterinarycare',
    'healthandbeautybusiness', 'beautysalon', 'dayspa', 'hairsalon',
    'nailsalon', 'tattooparlor', 'homeandconstructionbusiness', 'electrician',
    'generalcontractor', 'hvacbusiness', 'housepainter', 'locksmith',
    'movingcompany', 'plumber', 'roofingcontractor', 'professionalservice',
    'accountingservice', 'attorney', 'legalservice', 'insuranceagency',
    'notary', 'realestateagent', 'financialservice', 'bank',
    'automotivebusiness', 'autobodyshop', 'autodealer', 'autorental',
    'autorepair', 'autowash', 'gasstation', 'motorcyclerepair', 'childcare',
    'drycleaningorlaundry', 'emergencyservice', 'employmentagency',
    'entertainmentbusiness', 'exercisegym', 'gym', 'healthclub',
    'lodgingbusiness', 'hotel', 'selfstorage', 'shoppingcenter',
    'sportsactivitylocation', 'travelagency', 'recyclingcenter',
    'animalshelter', 'campground',
})


def _origine(texte: str, plat: str, debut: int, fin: int):
    """Map a span found on the folded copy back onto `texte`.

    `_plat` collapses whitespace runs and strips accents, which shifts every
    character offset, but it never splits or merges tokens. Counting tokens is
    therefore the only mapping that survives the fold.
    """
    spans = [match.span() for match in _RE_MOT.finditer(texte)]
    mots = plat.split()
    if not spans or len(spans) != len(mots):
        return None
    premier = len(plat[:debut].split())
    dernier = max(premier + 1, len(plat[:fin].split()))
    if premier >= len(spans):
        return None
    dernier = min(dernier, len(spans))
    return spans[premier][0], spans[dernier - 1][1]


def _lire_tel(match) -> dict:
    """Turn one phone match into its digits and its Quebec display form."""
    indicatif = match.group('ind1') or match.group('ind2')
    prefixe = match.group('pre')
    ligne = match.group('lig')
    poste = match.group('poste') or ''
    affiche = f'({indicatif}) {prefixe}-{ligne}'
    if poste:
        affiche += f' poste {poste}'
    return {
        'valeur': affiche,
        'chiffres': indicatif + prefixe + ligne,
        'poste': poste,
        'brut': ' '.join(match.group(0).split()),
    }


def _lire_province(texte: str, plat: str, span_ville) -> str:
    """Two-letter province code found on the line, or ''.

    The spelled-out name is only accepted where it is not the city itself:
    "Québec (Québec)" holds both, and reading the first one as the province
    would lose the city on every address in the capital.
    """
    code = _RE_PROVINCE_CODE.search(texte)
    if code:
        return _PROVINCES.get(code.group(1).lower(), code.group(1).upper())
    for match in _RE_PROVINCE_NOM.finditer(plat):
        span = _origine(texte, plat, *match.span())
        if span_ville and span and span == span_ville:
            continue
        trouve = _PROVINCES.get(_plat(match.group(0)))
        if trouve:
            return trouve
    return ''


def _nom_de_voie(texte, plat, civique, unite, code, span_ville) -> str:
    """The street as written: filler tokens, generic, and the name after it.

    The name runs to the first separator. The city and the unit are cut points
    of their own because a footer line often writes "1234 rue Principale
    Chicoutimi" with no comma anywhere.
    """
    debut = civique.start('avant')
    fin = len(texte)
    apres = civique.end()
    positions = [
        texte.find(',', apres),
        texte.find(';', apres),
        texte.find('(', apres),
        unite.start() if unite and unite.start() > apres else -1,
        code.start() if code and code.start() > apres else -1,
        span_ville[0] if span_ville and span_ville[0] > apres else -1,
    ]
    for position in positions:
        if 0 <= position < fin:
            fin = position
    return ' '.join(texte[debut:fin].split())


def _lire_adresse(ligne: str) -> dict | None:
    """Parse one line into address components, or None when it is not one.

    Nothing here is mandatory on its own: a footer often carries the street
    alone and leaves the city to the page title, while a citation carries the
    city and the postal code with no civic number. `pieces` says how much was
    found so the caller can demand more from a loose source than from a
    structured one.
    """
    if not ligne:
        return None
    texte = _RE_STOP_ADRESSE.split(ligne, 1)[0]
    texte = texte.strip().strip(',;:').strip()
    if not texte or len(texte) > 200:
        return None

    plat = _plat(texte)
    civique = _RE_CIVIQUE.search(texte)
    code = _RE_CODE_POSTAL.search(texte)
    unite = _RE_UNITE.search(texte)

    ville, span_ville = '', None
    trouve = _RE_VILLE.search(plat)
    if trouve:
        span_ville = _origine(texte, plat, *trouve.span())
        if span_ville:
            # The span covers whole tokens, so the comma that follows the city
            # on "Chicoutimi, Quebec" comes along and has to go.
            ville = texte[span_ville[0]:span_ville[1]].strip(' ,;.:()')
        else:
            ville = trouve.group(0)
    province = _lire_province(texte, plat, span_ville)

    pieces = sum(1 for valeur in (civique, code, ville, province) if valeur)
    if not pieces:
        return None

    return {
        'valeur': texte,
        'numero': ' '.join(civique.group('numero').split()) if civique else '',
        'voie': _nom_de_voie(texte, plat, civique, unite, code, span_ville)
                if civique else '',
        'unite': unite.group('unite') if unite else '',
        'ville': ville,
        'province': province,
        'code_postal': (code.group(1) + ' ' + code.group(2)).upper() if code else '',
        'pieces': pieces,
    }


def _ligne_adresse(composants: dict) -> str:
    """Rebuild a readable address line from components, French order.

    Accepts both this module's keys and schema.org's, so a PostalAddress read
    from JSON-LD and a hand-filled dict both come out the same way.
    """
    rue = _mot(composants, 'rue', 'voie', 'streetaddress', 'street_address', 'adresse')
    if not rue:
        numero = _mot(composants, 'numero')
        voie = _mot(composants, 'voie')
        rue = ' '.join(part for part in (numero, voie) if part)
    ville = _mot(composants, 'ville', 'addresslocality', 'locality', 'city')
    province = _mot(composants, 'province', 'addressregion', 'region', 'state')
    postal = _mot(composants, 'code_postal', 'postalcode', 'postal_code', 'zip')
    unite = _mot(composants, 'unite', 'app', 'suite')

    morceaux = [part for part in (rue, f'app. {unite}' if unite else '', ville) if part]
    ligne = ', '.join(morceaux)
    if province:
        ligne = f'{ligne} ({province})' if ligne else f'({province})'
    if postal:
        ligne = f'{ligne} {postal}'.strip()
    return ' '.join(ligne.split())


def _mot(source: dict, *cles) -> str:
    """First non-empty string among `cles`, keys read case-insensitively."""
    if not isinstance(source, dict):
        return ''
    plat = {str(cle).strip().lower(): valeur for cle, valeur in source.items()}
    for cle in cles:
        valeur = plat.get(cle)
        if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
            valeur = str(valeur)
        if isinstance(valeur, str) and valeur.strip():
            return ' '.join(valeur.split())
    return ''


def _nom_valide(nom: str) -> bool:
    """Reject the boilerplate that sits where a business name would sit."""
    nom = ' '.join((nom or '').split()).strip(' .,;:-')
    if not 2 <= len(nom) <= 70:
        return False
    if not any(caractere.isalpha() for caractere in nom):
        return False
    return not _RE_NON_NOM.match(_plat(nom))


def _nettoie_nom(nom: str) -> str:
    return ' '.join((nom or '').split()).strip(' .,;:-')


# ---------------------------------------------------------------------------
# Normalization: what has to happen before two sources are compared
# ---------------------------------------------------------------------------

def _normalise_nom(valeur: str) -> str:
    """Comparable business name: folded, legal form and punctuation dropped.

    "Plomberie Rive-Nord inc." and "Plomberie Rive Nord" are the same business,
    and reporting them as a NAP divergence sends a client chasing nothing.
    """
    plat = _plat(valeur)
    plat = _RE_FORME_JURIDIQUE.sub(' ', plat)
    jetons = [jeton for jeton in re.split(r"[^\w']+", plat) if jeton.strip("'")]
    return ' '.join(jetons)


def _normalise_tel(valeur) -> tuple[str, str]:
    """(ten digits, extension) whatever separators the source used."""
    if isinstance(valeur, dict):
        valeur = valeur.get('valeur') or valeur.get('telephone') or ''
    texte = str(valeur or '')
    match = _RE_TEL.search(texte)
    if match:
        lu = _lire_tel(match)
        return lu['chiffres'], lu['poste']
    chiffres = ''.join(c for c in texte if c.isdigit())
    if len(chiffres) == 11 and chiffres.startswith('1'):
        chiffres = chiffres[1:]
    return (chiffres if len(chiffres) == 10 else ''), ''


def _normalise_adresse(valeur: str) -> str:
    """Comparable address: abbreviations expanded, ordinals and codes folded.

    This is the whole reason the module exists in two steps. A site writing
    "1234, boul. Talbot" and a Google listing writing "1234 boulevard Talbot"
    hold one address; comparing the raw strings reports a divergence that a
    client would spend an afternoon failing to fix.
    """
    plat = _plat(valeur)
    plat = _RE_CODE_POSTAL.sub(lambda m: (m.group(1) + m.group(2)).lower(), plat)
    plat = _RE_ORDINAL.sub(r'\1', plat)
    plat = _RE_PROVINCE_NOM.sub(
        lambda m: _PROVINCES.get(_plat(m.group(0)), m.group(0)).lower(), plat,
    )
    jetons = []
    for brut in re.split(r"[^\w']+", plat):
        jeton = brut.strip("'")
        if not jeton:
            continue
        jeton = _ABREVIATIONS_VOIE.get(jeton, jeton)
        if jeton:
            jetons.append(jeton)
    return ' '.join(jetons)


def _normalise_composant(champ: str, valeur: str) -> str:
    if champ == 'code_postal':
        plat = _plat(valeur).replace(' ', '')
        return plat
    if champ == 'province':
        return _PROVINCES.get(_plat(valeur), _plat(valeur))
    if champ == 'unite':
        return _plat(valeur).lstrip('#').strip('.')
    return _normalise_adresse(valeur)


# ---------------------------------------------------------------------------
# Public: NAP extraction
# ---------------------------------------------------------------------------

def _candidat(candidats: list, source: str, valeur: str, cle: str, **extra) -> None:
    """Record one finding with the region of the page it was read from."""
    valeur = ' '.join((valeur or '').split())
    if not valeur or not cle:
        return
    libelle, rang = _SOURCES[source]
    entree = {'valeur': valeur, 'source': source, 'libelle_source': libelle,
              'rang': rang, 'cle': cle}
    entree.update(extra)
    candidats.append(entree)


def _classer(candidats: list) -> list:
    """Dedupe by comparable key, keeping the most trusted source of each value."""
    garde: dict[str, dict] = {}
    for ordre, item in enumerate(candidats):
        ancien = garde.get(item['cle'])
        if ancien is None:
            garde[item['cle']] = dict(item, ordre=ordre)
        elif item['rang'] < ancien['rang']:
            garde[item['cle']] = dict(item, ordre=ancien['ordre'])
    classes = sorted(garde.values(), key=lambda item: (item['rang'], item['ordre']))
    return [
        {cle: valeur for cle, valeur in item.items() if cle not in ('rang', 'ordre', 'cle')}
        for item in classes[:_MAX_CANDIDATS]
    ]


def _entites_locales(schema) -> list:
    """JSON-LD entities that describe a place of business."""
    sorties = []
    for bloc in schema or []:
        if not isinstance(bloc, dict):
            continue
        brut = bloc.get('@type')
        types = brut if isinstance(brut, list) else [brut]
        plats = {_plat(t).replace(' ', '') for t in types if isinstance(t, str)}
        if plats & _TYPES_LOCAUX or 'organization' in plats:
            sorties.append(bloc)
        elif bloc.get('address') or bloc.get('telephone'):
            sorties.append(bloc)
    return sorties


def _adresse_jsonld(bloc) -> str:
    adresse = bloc.get('address')
    if isinstance(adresse, list):
        adresse = adresse[0] if adresse else None
    if isinstance(adresse, str):
        return ' '.join(adresse.split())
    if isinstance(adresse, dict):
        return _ligne_adresse(adresse)
    return ''


def _nap_jsonld(signals, noms, tels, adresses) -> None:
    for bloc in _entites_locales(signals.get('schema')):
        nom = _mot(bloc, 'name', 'legalname')
        if _nom_valide(nom):
            _candidat(noms, 'jsonld', _nettoie_nom(nom), _normalise_nom(nom))
        for match in _RE_TEL.finditer(_mot(bloc, 'telephone')):
            lu = _lire_tel(match)
            _candidat(tels, 'jsonld', lu['valeur'], lu['chiffres'] + lu['poste'],
                      chiffres=lu['chiffres'], poste=lu['poste'])
        ligne = _adresse_jsonld(bloc)
        lue = _lire_adresse(ligne)
        if lue:
            _candidat(adresses, 'jsonld', lue['valeur'],
                      _normalise_adresse(lue['valeur']), composants=lue)


def _nap_microdata(scan, noms, tels, adresses) -> None:
    donnees = scan.microdata
    nom = donnees.get('name') or donnees.get('legalname') or ''
    if _nom_valide(nom):
        _candidat(noms, 'microdata', _nettoie_nom(nom), _normalise_nom(nom))
    for match in _RE_TEL.finditer(donnees.get('telephone', '')):
        lu = _lire_tel(match)
        _candidat(tels, 'microdata', lu['valeur'], lu['chiffres'] + lu['poste'],
                  chiffres=lu['chiffres'], poste=lu['poste'])
    ligne = _ligne_adresse({
        'rue': donnees.get('streetaddress', ''),
        'ville': donnees.get('addresslocality', ''),
        'province': donnees.get('addressregion', ''),
        'code_postal': donnees.get('postalcode', ''),
    })
    lue = _lire_adresse(ligne)
    if lue:
        _candidat(adresses, 'microdata', lue['valeur'],
                  _normalise_adresse(lue['valeur']), composants=lue)


def _nap_liens(scan, tels) -> None:
    for href in scan.tel_hrefs[:_MAX_CANDIDATS]:
        for match in _RE_TEL.finditer(href):
            lu = _lire_tel(match)
            _candidat(tels, 'lien_tel', lu['valeur'], lu['chiffres'] + lu['poste'],
                      chiffres=lu['chiffres'], poste=lu['poste'])


def _nap_lignes(lignes, source, tels, adresses, noms=None, seuil=1) -> None:
    """Read one region of the page: its phones, its addresses, its copyright."""
    for ligne in lignes:
        for match in _RE_TEL.finditer(ligne):
            lu = _lire_tel(match)
            _candidat(tels, source, lu['valeur'], lu['chiffres'] + lu['poste'],
                      chiffres=lu['chiffres'], poste=lu['poste'])
        lue = _lire_adresse(ligne)
        if lue and lue['pieces'] >= seuil and (lue['numero'] or lue['code_postal']):
            _candidat(adresses, source, lue['valeur'],
                      _normalise_adresse(lue['valeur']), composants=lue)
        if noms is None:
            continue
        droits = _RE_COPYRIGHT.search(ligne)
        if droits and _nom_valide(droits.group('nom')):
            nom = _nettoie_nom(droits.group('nom'))
            _candidat(noms, source, nom, _normalise_nom(nom))


def _nap_entete(signals, noms) -> None:
    site = (signals.get('open_graph') or {}).get('og:site_name', '')
    if _nom_valide(site):
        _candidat(noms, 'meta_og', _nettoie_nom(site), _normalise_nom(site))

    titre = signals.get('title') or ''
    segments = [part.strip() for part in _RE_SEPARATEUR_TITRE.split(titre) if part.strip()]
    # The brand sits at the end of a Quebec title ("Service à Ville | Marque"),
    # and a title with no separator is a topic, not a name.
    if len(segments) >= 2 and _nom_valide(segments[-1]):
        nom = _nettoie_nom(segments[-1])
        if len(nom.split()) <= 6:
            _candidat(noms, 'titre', nom, _normalise_nom(nom))


def _fiche_google(scan) -> dict:
    """What the page shows of its Google listing: a map, a link to the profile."""
    cibles = list(scan.hrefs) + list(scan.iframes)
    carte = any(_RE_CARTE.search(cible.lower()) for cible in cibles)
    fiche = any(_RE_FICHE_ID.search(cible.lower()) for cible in cibles)
    return {'carte': carte, 'fiche_google': fiche}


def extract_nap(html: str) -> dict:
    """Read the name, address and phone a page publishes, and where from.

    Every finding carries the region of the document it came from, ranked by
    how much Google trusts it: JSON-LD and microdata first, then the
    `<address>` block and the `tel:` link, then the footer, then loose page
    text. The winner of each field is the finding from the strongest source,
    which is what makes the result comparable with a Google listing rather than
    with whatever number happened to appear first in the markup.

    Returns:
        {
          'nom' / 'telephone' / 'adresse': the retained finding, or None. Each
              holds 'valeur', 'source', 'libelle_source', plus 'chiffres' and
              'poste' for a phone and 'composants' for an address.
          'candidats': every finding per field, best source first.
          'tel_cliquable', 'carte', 'fiche_google', 'formulaire': what the page
              offers a visitor who wants to reach or find the business.
          'complet': the three fields were found.
          'champs_manquants': the ones that were not.
        }

    Reads only what it is handed: no network, and a broken document still gives
    back whatever was readable before the markup broke.
    """
    document = html if isinstance(html, str) else ''
    signals = extract_seo_signals(document)
    scan = _scan(document)

    noms: list[dict] = []
    tels: list[dict] = []
    adresses: list[dict] = []

    _nap_jsonld(signals, noms, tels, adresses)
    _nap_microdata(scan, noms, tels, adresses)
    _nap_liens(scan, tels)
    _nap_lignes(_lignes(scan.adresse_parts)[:60], 'balise_address', tels, adresses)
    _nap_lignes(_lignes(scan.pied_parts)[:200], 'pied_de_page', tels, adresses,
                noms=noms, seuil=2)
    _nap_entete(signals, noms)
    _nap_lignes(_lignes(scan.parts)[:600], 'texte', tels, adresses, seuil=2)

    champs = {
        'nom': _classer(noms),
        'telephone': _classer(tels),
        'adresse': _classer(adresses),
    }
    manquants = [champ for champ, trouves in champs.items() if not trouves]
    sortie = {
        champ: (trouves[0] if trouves else None) for champ, trouves in champs.items()
    }
    sortie.update({
        'candidats': champs,
        'tel_cliquable': bool(scan.tel_hrefs),
        'formulaire': scan.formulaire,
        'complet': not manquants,
        'champs_manquants': manquants,
    })
    sortie.update(_fiche_google(scan))
    return sortie


# ---------------------------------------------------------------------------
# Public: NAP consistency across sources
# ---------------------------------------------------------------------------

_CHAMPS_NAP = ('nom', 'adresse', 'telephone')

_LIBELLES_CHAMPS = {
    'nom': "Nom de l'entreprise",
    'adresse': 'Adresse',
    'telephone': 'Téléphone',
}

# What each disagreement costs the business. A wrong number is a lost call the
# day it is dialled; a missing apartment number costs a delivery once in a
# while. The two cannot carry the same badge in a report.
_SEVERITE_CHAMP = {
    'nom': 'moyenne',
    'adresse': 'elevee',
    'telephone': 'critique',
}

_COMPOSANTS_ADRESSE = ('numero', 'voie', 'unite', 'ville', 'province', 'code_postal')

_SEVERITE_COMPOSANT = {
    'numero': 'critique',
    'voie': 'elevee',
    'ville': 'elevee',
    'province': 'moyenne',
    'code_postal': 'moyenne',
    'unite': 'faible',
}

# The article travels with the label so the sentence that quotes it stays
# French: "sur le numéro civique", "sur la ville".
_LIBELLES_COMPOSANTS = {
    'numero': 'le numéro civique',
    'voie': 'la voie',
    'unite': "le numéro d'appartement ou de local",
    'ville': 'la ville',
    'province': 'la province',
    'code_postal': 'le code postal',
}

_RANG_SEVERITE = {nom: rang for rang, nom in enumerate(reversed(SEVERITES))}


def _pire(severites) -> str:
    """The most severe of the lot, 'aucune' when there is nothing."""
    retenue = 'aucune'
    for severite in severites:
        if _RANG_SEVERITE.get(severite, 99) < _RANG_SEVERITE[retenue]:
            retenue = severite
    return retenue


def _libelle_source(entree, rang: int) -> str:
    for cle in ('source', 'libelle', 'nom_source', 'origine'):
        valeur = entree.get(cle)
        if isinstance(valeur, str) and valeur.strip():
            return valeur.strip()
    return f'Source {rang}'


def _valeur_source(entree: dict, champ: str) -> str:
    """The raw value of one field, whatever shape the caller passed.

    A string, the finding dict `extract_nap` returns, or a dict of components:
    all three arrive here, so the output of one function feeds the other with
    nothing in between.
    """
    valeur = entree.get(champ)
    if valeur is None:
        alias = {'nom': ('name',), 'adresse': ('address',),
                 'telephone': ('tel', 'phone', 'tel_phone')}[champ]
        for cle in alias:
            if entree.get(cle) is not None:
                valeur = entree[cle]
                break
    if isinstance(valeur, dict):
        brut = valeur.get('valeur') or valeur.get('value') or ''
        if not brut and champ == 'adresse':
            brut = _ligne_adresse(valeur)
        if not brut and champ == 'telephone':
            brut = _mot(valeur, 'telephone', 'numero', 'chiffres')
        valeur = brut
    if not isinstance(valeur, str):
        return ''
    return ' '.join(valeur.split())


def _composants_source(entree: dict, brut: str) -> dict | None:
    """Address components of one source, from its own dict or from the line."""
    valeur = entree.get('adresse')
    if isinstance(valeur, dict):
        composants = valeur.get('composants')
        if isinstance(composants, dict):
            return composants
    # A caller who splits the civic number off the street and one who leaves it
    # in front of it must produce the same components, so the rebuilt line is
    # parsed rather than trusted field by field.
    lue = _lire_adresse(brut)
    if lue is not None:
        return lue
    if isinstance(valeur, dict):
        interne = {
            champ: _mot(valeur, champ, *_ALIAS_COMPOSANTS[champ])
            for champ in _COMPOSANTS_ADRESSE
        }
        if any(interne.values()):
            return interne
    return None


_ALIAS_COMPOSANTS = {
    'numero': ('number', 'no_civique'),
    'voie': ('rue', 'street', 'streetaddress'),
    'unite': ('app', 'suite', 'local', 'bureau'),
    'ville': ('addresslocality', 'locality', 'city'),
    'province': ('addressregion', 'region', 'state'),
    'code_postal': ('postalcode', 'postal_code', 'zip'),
}


def _divergence(champ, composant, severite, message, valeurs) -> dict:
    return {
        'champ': champ,
        'libelle_champ': _LIBELLES_CHAMPS[champ],
        'composant': composant,
        'severite': severite,
        'message': message,
        'valeurs': valeurs,
    }


def _compare_nom(lues, divergences) -> dict:
    normalisees = {nom['normalisee'] for nom in lues}
    if len(normalisees) <= 1:
        return {'coherent': True, 'severite': 'aucune'}

    jeux = [set(nom['normalisee'].split()) for nom in lues]
    inclus = all(
        a <= b or b <= a for index, a in enumerate(jeux) for b in jeux[index + 1:]
    )
    severite = 'faible' if inclus else _SEVERITE_CHAMP['nom']
    ecrits = ' contre '.join(f"« {nom['valeur']} »" for nom in lues)
    divergences.append(_divergence(
        'nom', None, severite,
        (f"Le nom diffère d'une source à l'autre : {ecrits}. "
         + ("Une source ajoute des mots que l'autre n'a pas : garde exactement la "
            "même dénomination partout, Google recoupe les mentions par le nom."
            if inclus else
            "Deux dénominations différentes pour un même établissement empêchent "
            "Google de relier les mentions entre elles.")),
        [{'source': nom['source'], 'valeur': nom['valeur']} for nom in lues],
    ))
    return {'coherent': False, 'severite': severite}


def _compare_tel(lues, divergences) -> dict:
    coeurs = {tel['normalisee'][0] for tel in lues}
    postes = {tel['normalisee'][1] for tel in lues}
    ecrits = ' contre '.join(f"« {tel['valeur']} »" for tel in lues)
    valeurs = [{'source': tel['source'], 'valeur': tel['valeur']} for tel in lues]

    if len(coeurs) > 1:
        divergences.append(_divergence(
            'telephone', None, _SEVERITE_CHAMP['telephone'],
            f"Deux numéros différents selon la source : {ecrits}. Un client sur deux "
            "compose celui qui ne mène nulle part, et l'appel est perdu sans que "
            "personne ne le sache.",
            valeurs,
        ))
        return {'coherent': False, 'severite': _SEVERITE_CHAMP['telephone']}

    if len(postes) > 1:
        divergences.append(_divergence(
            'telephone', 'poste', 'faible',
            f"Même numéro, poste différent : {ecrits}. Uniformise le poste ou "
            "retire-le des fiches externes.",
            valeurs,
        ))
        return {'coherent': False, 'severite': 'faible'}

    return {'coherent': True, 'severite': 'aucune'}


def _compare_adresse(lues, divergences) -> dict:
    composants = {}

    if all(item['composants'] for item in lues):
        severites = []
        for champ in _COMPOSANTS_ADRESSE:
            presentes = [
                (item, _normalise_composant(champ, _mot(item['composants'], champ)))
                for item in lues
            ]
            lisibles = [(item, valeur) for item, valeur in presentes if valeur]
            manquantes = [item['source'] for item, valeur in presentes if not valeur]
            distinctes = {valeur for _, valeur in lisibles}
            if len(lisibles) < 2 or len(distinctes) <= 1:
                composants[champ] = {
                    'coherent': True,
                    'severite': 'aucune',
                    'absent': manquantes,
                }
                continue
            severite = _SEVERITE_COMPOSANT[champ]
            severites.append(severite)
            composants[champ] = {
                'coherent': False,
                'severite': severite,
                'absent': manquantes,
                'valeurs': [
                    {'source': item['source'], 'valeur': _mot(item['composants'], champ)}
                    for item, _ in lisibles
                ],
            }
            divergences.append(_divergence(
                'adresse', champ, severite,
                f"L'adresse diverge sur {_LIBELLES_COMPOSANTS[champ]} : "
                + ' contre '.join(
                    f"« {_mot(item['composants'], champ)} »" for item, _ in lisibles
                ) + '.',
                [
                    {'source': item['source'], 'valeur': _mot(item['composants'], champ)}
                    for item, _ in lisibles
                ],
            ))
        if not severites:
            return {'coherent': True, 'severite': 'aucune', 'composants': composants}
        return {
            'coherent': False,
            'severite': _pire(severites),
            'composants': composants,
        }

    # One side could not be parsed, so the comparison falls back to the whole
    # normalized line: still abbreviation-proof, just unable to name what moved.
    if len({item['normalisee'] for item in lues}) <= 1:
        return {'coherent': True, 'severite': 'aucune', 'composants': composants}
    ecrits = ' contre '.join(f"« {item['valeur']} »" for item in lues)
    divergences.append(_divergence(
        'adresse', None, _SEVERITE_CHAMP['adresse'],
        f"L'adresse diffère d'une source à l'autre : {ecrits}. Reprends la même "
        "écriture partout, en commençant par la fiche Google.",
        [{'source': item['source'], 'valeur': item['valeur']} for item in lues],
    ))
    return {
        'coherent': False,
        'severite': _SEVERITE_CHAMP['adresse'],
        'composants': composants,
    }


def compare_nap(sources: list) -> dict:
    """Compare the NAP of several sources and report where they disagree.

    Every value is normalized before anything is compared: case and accents
    folded, street abbreviations expanded, legal forms dropped from the name,
    phone numbers reduced to their digits. Without that step "boul." against
    "boulevard" and "(418) 555-1234" against "418-555-1234" come back as
    divergences, and a client burns an afternoon fixing what was never broken.

    Args:
        sources: one dict per source. `source` names it in the report; `nom`,
            `adresse` and `telephone` hold the values, as plain strings, as the
            finding dicts `extract_nap` returns, or as a dict of components.

    Returns:
        {
          'coherent': True when nothing diverges,
          'severite': the worst level found, taken from SEVERITES,
          'sources': the names compared,
          'champs': per field, {'coherent', 'severite', 'valeurs', 'absent'},
                    the address also carrying 'composants',
          'divergences': one entry per disagreement, worst first,
          'resume': one French sentence for a report header,
        }

    Fewer than two sources holding a field is not a divergence: it is a
    comparison that could not happen, and it is reported as such.
    """
    entrees = [item for item in (sources or []) if isinstance(item, dict)]
    noms_sources = [_libelle_source(item, rang + 1) for rang, item in enumerate(entrees)]

    champs = {}
    divergences: list[dict] = []
    for champ in _CHAMPS_NAP:
        lues = []
        absentes = []
        for entree, nom_source in zip(entrees, noms_sources):
            brut = _valeur_source(entree, champ)
            if not brut:
                absentes.append(nom_source)
                continue
            item = {'source': nom_source, 'valeur': brut}
            if champ == 'nom':
                item['normalisee'] = _normalise_nom(brut)
            elif champ == 'telephone':
                item['normalisee'] = _normalise_tel(brut)
            else:
                item['normalisee'] = _normalise_adresse(brut)
                item['composants'] = _composants_source(entree, brut)
            lues.append(item)

        etat = {
            'coherent': True,
            'severite': 'aucune',
            'comparees': len(lues),
            'absent': absentes,
            'valeurs': [
                {'source': item['source'], 'valeur': item['valeur']} for item in lues
            ],
        }
        if len(lues) >= 2:
            if champ == 'nom':
                etat.update(_compare_nom(lues, divergences))
            elif champ == 'telephone':
                etat.update(_compare_tel(lues, divergences))
            else:
                etat.update(_compare_adresse(lues, divergences))
        if lues and absentes:
            divergences.append(_divergence(
                champ, 'absent', 'faible',
                f"{_LIBELLES_CHAMPS[champ]} absent de : {', '.join(absentes)}. "
                "Une fiche incomplète compte moins qu'une fiche contradictoire, mais "
                "elle ne confirme rien non plus.",
                etat['valeurs'],
            ))
            etat['severite'] = _pire([etat['severite'], 'faible'])
        champs[champ] = etat

    divergences.sort(key=lambda item: _RANG_SEVERITE.get(item['severite'], 99))
    severite = _pire(item['severite'] for item in divergences)
    reelles = [item for item in divergences if item['composant'] != 'absent']

    if len(entrees) < 2:
        resume = ("Une seule source fournie : la cohérence NAP se vérifie à partir de "
                  "deux sources.")
    elif not divergences:
        resume = f"NAP cohérent sur les {len(entrees)} sources comparées."
    else:
        resume = (
            f"{len(divergences)} écart(s) sur {len(entrees)} sources, "
            f"gravité maximale : {severite}."
        )

    return {
        'coherent': not reelles,
        'severite': severite,
        'sources': noms_sources,
        'champs': champs,
        'divergences': divergences,
        'resume': resume,
    }


# ---------------------------------------------------------------------------
# Public: the six weighted dimensions
# ---------------------------------------------------------------------------

class _Grille:
    """Collects measured checks per dimension and renders the report.

    A check reports a ratio in [0, 1] and a weight relative to the other checks
    of its dimension, so skipping one redistributes its weight instead of
    charging the site for it. A dimension where nothing could be measured
    leaves the denominator entirely.
    """

    def __init__(self):
        self._dim = {
            cle: {'gagne': 0.0, 'possible': 0.0, 'faites': 0, 'ignorees': [],
                  'constats': [], 'problemes': []}
            for cle, _, _ in DIMENSIONS
        }
        self._recos: list[dict] = []

    def constat(self, dimension: str, texte: str) -> None:
        if texte:
            self._dim[dimension]['constats'].append(texte)

    def ignore(self, dimension: str, raison: str) -> None:
        """Mark one check as not measurable. It leaves the denominator."""
        self._dim[dimension]['ignorees'].append(raison)

    def verifie(self, dimension: str, code: str, poids: float, ratio,
                *, constat: str = '', probleme: str = '', action: str = '',
                severite: str = 'moyenne') -> None:
        ratio = 1.0 if ratio is True else 0.0 if ratio is False else float(ratio)
        ratio = max(0.0, min(1.0, ratio))
        bloc = self._dim[dimension]
        bloc['gagne'] += poids * ratio
        bloc['possible'] += poids
        bloc['faites'] += 1

        if ratio >= 1.0:
            self.constat(dimension, constat)
            return
        if probleme:
            bloc['problemes'].append(probleme)
        self._recos.append({
            'dimension': dimension,
            'code': code,
            'severite': severite if severite in _RANG_SEVERITE else 'moyenne',
            'manque': poids * (1.0 - ratio),
            'probleme': probleme,
            'action': action,
        })

    def resultat(self) -> dict:
        dimensions = {}
        non_mesurees = []
        total_gagne = 0.0
        total_max = 0.0

        for cle, libelle, poids in DIMENSIONS:
            bloc = self._dim[cle]
            applicable = bloc['possible'] > 0
            note = None
            score = 0.0

            if applicable:
                ratio = bloc['gagne'] / bloc['possible']
                score = round(ratio * poids, 1)
                note = int(round(ratio * 100))
                total_gagne += score
                total_max += poids
            else:
                non_mesurees.append(cle)

            for reco in self._recos:
                if reco['dimension'] == cle:
                    reco['points_recuperables'] = round(
                        reco['manque'] / bloc['possible'] * poids, 1,
                    )
                    reco['libelle_dimension'] = libelle

            if not applicable:
                statut = 'non_mesure'
            elif note < 70:
                statut = 'echec'
            elif note < 90:
                statut = 'attention'
            else:
                statut = 'reussi'

            dimensions[cle] = {
                'libelle': libelle,
                'poids': poids,
                'score': score,
                'max': float(poids) if applicable else 0.0,
                'note': note,
                'applicable': applicable,
                'statut': statut,
                'constats': bloc['constats'],
                'problemes': bloc['problemes'],
                'verifications': {'faites': bloc['faites'],
                                  'ignorees': len(bloc['ignorees'])},
                'non_mesure': list(dict.fromkeys(r for r in bloc['ignorees'] if r)),
            }

        recommandations = sorted(
            (
                {
                    'dimension': reco['dimension'],
                    'libelle_dimension': reco['libelle_dimension'],
                    'code': reco['code'],
                    'severite': reco['severite'],
                    'points_recuperables': reco['points_recuperables'],
                    'probleme': reco['probleme'],
                    'action': reco['action'],
                }
                for reco in self._recos
            ),
            key=lambda reco: (-reco['points_recuperables'],
                              _RANG_SEVERITE[reco['severite']]),
        )

        score = int(round(total_gagne / total_max * 100)) if total_max else None
        return {
            'score': score,
            'dimensions': dimensions,
            'recommandations': recommandations,
            'couverture': round(total_max, 1),
            'dimensions_non_mesurees': non_mesurees,
        }


def _entier(valeur):
    if isinstance(valeur, bool) or valeur is None:
        return None
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _reel(valeur):
    if isinstance(valeur, bool) or valeur is None:
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _age_jours(valeur):
    """Days since `valeur`, which may be a date, a datetime or an ISO string."""
    if isinstance(valeur, datetime):
        valeur = valeur.date()
    elif isinstance(valeur, str):
        try:
            valeur = date.fromisoformat(valeur.strip()[:10])
        except ValueError:
            return None
    if not isinstance(valeur, date):
        return None
    return (date.today() - valeur).days


def _lieux(texte) -> dict:
    """Quebec places named in a text: which ones, and how often."""
    plat = _plat(texte)
    villes = _RE_VILLE.findall(plat)
    regions = _RE_REGION.findall(plat)
    return {
        'villes': sorted(set(villes)),
        'regions': sorted(set(regions)),
        'noms': sorted(set(villes) | set(regions)),
        'total': len(villes) + len(regions),
    }


def _texte_de(valeur) -> str:
    return valeur.strip() if isinstance(valeur, str) else ''


def _dim_fiche(grille, gbp) -> None:
    cle = 'fiche_google'
    # The dimension scores the listing itself, never the page. What the page
    # shows of it (a map, a link to the profile) is a page signal and is scored
    # there, otherwise a quarter of the grade would rest on one anchor.
    if not isinstance(gbp, dict):
        grille.ignore(cle, "Fiche Google non fournie : le profil lui-même n'a pas été évalué.")
        return

    _verifie_bool(
        grille, cle, gbp, ('revendiquee', 'verifiee', 'claimed'), 'gbp_revendiquee', 6,
        constat="La fiche Google est revendiquée et vérifiée.",
        probleme="La fiche Google n'est pas revendiquée : n'importe qui peut en proposer une modification et personne ne reçoit les avis.",
        action="Revendique la fiche depuis google.com/business et fais la vérification (carte postale, téléphone ou vidéo selon ce que Google propose). Rien d'autre ne compte tant que ce n'est pas fait.",
        severite='critique',
        raison="Revendication de la fiche non renseignée.",
    )
    _verifie_bool(
        grille, cle, gbp, ('categorie', 'categorie_principale', 'category'),
        'gbp_categorie', 5,
        constat="Une catégorie principale est déclarée sur la fiche.",
        probleme="Aucune catégorie principale sur la fiche Google.",
        action="Choisis la catégorie principale la plus précise qui décrit ton métier, puis ajoute les catégories secondaires. C'est le critère qui décide dans quelles recherches locales la fiche peut apparaître.",
        severite='critique',
        raison="Catégorie de la fiche non renseignée.",
    )

    description = _texte_de(gbp.get('description'))
    if 'description' not in gbp:
        grille.ignore(cle, "Description de la fiche non renseignée.")
    else:
        grille.verifie(
            cle, 'gbp_description', 2,
            1.0 if len(description) >= 150 else 0.5 if description else 0.0,
            constat="La fiche porte une description étoffée.",
            probleme=("La description de la fiche est vide." if not description
                      else f"La description de la fiche ne fait que {len(description)} caractères."),
            action="Écris 750 caractères qui nomment le métier, les villes desservies et ce qui te distingue. La description ne classe pas la fiche, mais c'est le texte que lit un client hésitant.",
            severite='faible',
        )

    _verifie_bool(
        grille, cle, gbp, ('horaires', 'heures', 'hours'), 'gbp_horaires', 4,
        constat="Les heures d'ouverture sont renseignées.",
        probleme="Aucune heure d'ouverture sur la fiche Google.",
        action="Remplis les heures, et surtout les heures spéciales des jours fériés. « Ouvert » affiché à tort un 24 juin coûte un client et un avis d'une étoile.",
        severite='elevee',
        raison="Heures d'ouverture non renseignées.",
    )

    photos = _entier(gbp.get('photos'))
    if photos is None:
        grille.ignore(cle, "Nombre de photos de la fiche non renseigné.")
    else:
        grille.verifie(
            cle, 'gbp_photos', 3,
            1.0 if photos >= 10 else 0.5 if photos >= 3 else 0.0,
            constat=f"{photos} photos sur la fiche.",
            probleme=f"Seulement {photos} photo(s) sur la fiche Google.",
            action="Publie au moins dix photos réelles : la devanture, l'équipe, les travaux terminés. Les photos de banque d'images se repèrent et n'inspirent rien.",
            severite='moyenne',
        )

    publication = gbp.get('derniere_publication', gbp.get('derniere_pub'))
    jours = _age_jours(publication)
    if jours is None:
        grille.ignore(cle, "Date de la dernière publication de la fiche non renseignée.")
    else:
        grille.verifie(
            cle, 'gbp_publications', 3,
            1.0 if jours <= 30 else 0.5 if jours <= 90 else 0.0,
            constat=f"Dernière publication il y a {jours} jour(s).",
            probleme=f"Dernière publication sur la fiche il y a {jours} jours.",
            action="Publie une nouveauté par mois : un chantier terminé, une offre, un rappel saisonnier. Une fiche vivante est une fiche que Google montre.",
            severite='faible',
        )

    _verifie_bool(
        grille, cle, gbp, ('site_web', 'site', 'website'), 'gbp_site', 2,
        constat="La fiche pointe vers le site web.",
        probleme="Aucune adresse de site web sur la fiche Google.",
        action="Renseigne le site dans la fiche, et fais-le pointer vers la page de la ville concernée plutôt que vers l'accueil quand il y en a une.",
        severite='moyenne',
        raison="Adresse du site sur la fiche non renseignée.",
    )


def _verifie_bool(grille, cle, source, alias, code, poids, *, constat, probleme,
                  action, severite, raison) -> None:
    """Score a yes/no field of the listing, or drop the check when unknown.

    Absence of a key means nobody looked, which is not the same finding as a
    field the owner left empty, so it leaves the denominator instead.
    """
    for nom in alias:
        if nom in source:
            grille.verifie(cle, code, poids, bool(source.get(nom)),
                           constat=constat, probleme=probleme, action=action,
                           severite=severite)
            return
    grille.ignore(cle, raison)


def _dim_avis(grille, reviews) -> None:
    cle = 'avis'
    if not isinstance(reviews, dict):
        grille.ignore(cle, "Aucune donnée d'avis fournie : la réputation n'a pas été évaluée.")
        return

    total = _entier(reviews.get('total', reviews.get('nombre')))
    if total is None:
        grille.ignore(cle, "Nombre d'avis non renseigné.")
    else:
        grille.verifie(
            cle, 'avis_volume', 6,
            1.0 if total >= 25 else 0.5 if total >= 10 else 0.0,
            constat=f"{total} avis sur la fiche.",
            probleme=f"Seulement {total} avis sur la fiche Google.",
            action="Demande l'avis à chaque client satisfait, sur place et le jour même, avec un lien court vers le formulaire. Vise 25 avis avant de viser la moyenne parfaite.",
            severite='elevee',
        )

    moyenne = _reel(reviews.get('moyenne', reviews.get('note')))
    if moyenne is None:
        grille.ignore(cle, "Note moyenne non renseignée.")
    else:
        grille.verifie(
            cle, 'avis_note', 6,
            1.0 if moyenne >= 4.3 else 0.5 if moyenne >= 4.0 else 0.0,
            constat=f"Note moyenne de {moyenne:.1f}".replace('.', ',') + " sur 5.",
            probleme=f"Note moyenne de {moyenne:.1f}".replace('.', ',')
                     + " sur 5. Sous 4,0, la note devient le premier motif de rejet dans le pack local.",
            action="Réponds à chaque avis négatif en nommant le problème et ce que tu as changé, puis fais remonter la moyenne avec des avis récents. Un avis d'une étoile sans réponse pèse deux fois.",
            severite='elevee',
        )

    taux = _reel(reviews.get('taux_reponse'))
    if taux is None:
        repondus = _entier(reviews.get('repondus'))
        if repondus is not None and total:
            taux = repondus / total
    if taux is None:
        grille.ignore(cle, "Taux de réponse aux avis non renseigné.")
    else:
        taux = taux / 100 if taux > 1 else taux
        grille.verifie(
            cle, 'avis_reponses', 5,
            1.0 if taux >= 0.8 else 0.5 if taux >= 0.4 else 0.0,
            constat=f"{round(taux * 100)} % des avis ont une réponse.",
            probleme=f"Seulement {round(taux * 100)} % des avis reçoivent une réponse.",
            action="Réponds à tous les avis, bons comme mauvais, dans la semaine. La réponse s'adresse au prochain lecteur, pas à celui qui a écrit.",
            severite='moyenne',
        )

    jours = _age_jours(reviews.get('dernier', reviews.get('dernier_avis')))
    if jours is None:
        grille.ignore(cle, "Date du dernier avis non renseignée.")
    else:
        grille.verifie(
            cle, 'avis_fraicheur', 3,
            1.0 if jours <= 60 else 0.5 if jours <= 180 else 0.0,
            constat=f"Dernier avis il y a {jours} jour(s).",
            probleme=f"Dernier avis il y a {jours} jours : la fiche a l'air abandonnée.",
            action="Reprends la demande d'avis en continu. Un flux régulier compte davantage qu'un paquet d'avis obtenus en une semaine, que Google traite avec méfiance.",
            severite='moyenne',
        )


def _dim_page(grille, signals, nap) -> None:
    cle = 'seo_local_page'
    titre = _texte_de(signals.get('title'))
    h1 = ' '.join(item for item in (signals.get('h1') or []) if isinstance(item, str))
    meta = _texte_de(signals.get('meta_description'))
    corps = _texte_de(signals.get('text'))

    if signals.get('title') is None:
        grille.ignore(cle, "Titre de la page non lu.")
    else:
        grille.verifie(
            cle, 'ville_titre', 5, bool(_lieux(titre)['total']),
            constat=f"Le titre nomme un lieu : {titre}",
            probleme="Le titre de la page ne nomme aucune ville ni région.",
            action="Mets la ville dans le titre, sous la forme « Service à Ville | Entreprise ». C'est le premier endroit où Google et le lecteur cherchent le territoire desservi.",
            severite='elevee',
        )

    if not h1:
        grille.ignore(cle, "Aucun H1 lu sur la page.")
    else:
        grille.verifie(
            cle, 'ville_h1', 4, bool(_lieux(h1)['total']),
            constat="Le H1 nomme la ville ou la région desservie.",
            probleme="Le H1 ne nomme aucun lieu.",
            action="Reformule le H1 avec le métier et la ville. Une page locale qui ne dit pas où elle exerce se retrouve en concurrence avec le pays entier.",
            severite='elevee',
        )

    if signals.get('meta_description') is None:
        grille.ignore(cle, "Méta description absente du document.")
    else:
        grille.verifie(
            cle, 'ville_meta', 2, bool(_lieux(meta)['total']),
            constat="La méta description nomme le territoire.",
            probleme="La méta description ne nomme aucun lieu.",
            action="Nomme la ville et l'offre dans la méta description. Elle ne classe pas, elle décide du clic dans une liste de résultats locaux qui se ressemblent tous.",
            severite='faible',
        )

    if not corps:
        grille.ignore(cle, "Aucun texte visible : le contenu local n'a pas été évalué.")
    else:
        lieux = _lieux(corps)
        grille.verifie(
            cle, 'contenu_local', 3,
            1.0 if lieux['total'] >= 3 else 0.5 if lieux['total'] >= 1 else 0.0,
            constat=f"{lieux['total']} mentions de lieux dans le contenu ({', '.join(lieux['noms'][:4])}).",
            probleme="Le contenu ne mentionne aucun lieu du Québec.",
            action="Parle du territoire comme quelqu'un qui y travaille : les quartiers desservis, les délais de déplacement, un chantier réel. Répéter le nom de la ville dix fois ne remplace pas une phrase qui prouve que tu y es.",
            severite='moyenne',
        )

    langue = _texte_de(signals.get('lang')).lower()
    if not langue:
        grille.ignore(cle, "Attribut lang absent de la balise html.")
    else:
        grille.verifie(
            cle, 'langue', 1, langue.startswith('fr'),
            constat=f"La page se déclare en « {langue} ».",
            probleme=f"La page se déclare en « {langue} » alors qu'elle vise un public québécois.",
            action="Mets lang=\"fr-CA\" sur la balise html. C'est ce que lisent les moteurs et les lecteurs d'écran pour choisir la prononciation et la langue de résultat.",
            severite='faible',
        )

    if not isinstance(nap, dict):
        grille.ignore(cle, "NAP de la page non fourni : sa présence à l'écran n'a pas été vérifiée.")
        return

    presents = sum(1 for champ in _CHAMPS_NAP if nap.get(champ))
    grille.verifie(
        cle, 'nap_page', 3, presents / 3,
        constat="Le nom, l'adresse et le téléphone sont lisibles sur la page.",
        probleme="Il manque sur la page : " + ', '.join(nap.get('champs_manquants') or []) + '.',
        action="Affiche le nom, l'adresse et le téléphone en texte, dans le pied de page de toutes les pages. En image, ils n'existent ni pour Google ni pour un lecteur d'écran.",
        severite='elevee',
    )
    grille.verifie(
        cle, 'contact_joignable', 2,
        bool(nap.get('tel_cliquable')) or bool(nap.get('formulaire')),
        constat="Le visiteur peut appeler ou écrire sans quitter la page.",
        probleme="Aucun lien tel: ni formulaire de contact sur la page.",
        action="Mets le numéro dans un lien « tel: » et garde un formulaire court. Sur téléphone, un numéro qu'il faut recopier à la main coûte la moitié des appels.",
        severite='moyenne',
    )
    grille.verifie(
        cle, 'lien_fiche', 2,
        bool(nap.get('fiche_google')) or bool(nap.get('carte')),
        constat="La page renvoie vers la fiche Google ou vers la carte de l'établissement.",
        probleme="Aucun lien vers la fiche Google ni carte intégrée sur la page.",
        action="Ajoute un lien vers la fiche Google, ou la carte de l'établissement. C'est le raccourci que prend un visiteur pressé, et un lien de plus entre le site et la fiche.",
        severite='faible',
    )


def _dim_nap(grille, nap) -> None:
    cle = 'nap_citations'
    if not isinstance(nap, dict):
        grille.ignore(cle, "Aucun NAP fourni : la cohérence des citations n'a pas été évaluée.")
        return

    manquants = nap.get('champs_manquants') or []
    presents = 3 - len(manquants)
    grille.verifie(
        cle, 'nap_complet', 6, presents / 3,
        constat="Le NAP complet a été trouvé sur la page.",
        probleme="NAP incomplet sur le site : il manque " + ', '.join(manquants) + '.',
        action="Publie les trois éléments au même endroit, en texte, et garde exactement la même écriture partout ailleurs. C'est cette écriture qui sert de référence à toutes les citations.",
        severite='elevee',
    )

    adresse = nap.get('adresse')
    if not adresse:
        grille.ignore(cle, "Aucune adresse trouvée : son balisage n'a pas été évalué.")
    else:
        source = adresse.get('source')
        grille.verifie(
            cle, 'nap_balise', 3,
            1.0 if source in ('jsonld', 'microdata') else 0.5 if source == 'balise_address' else 0.0,
            constat=f"L'adresse est publiée dans une source structurée ({adresse.get('libelle_source')}).",
            probleme=f"L'adresse n'existe que dans le texte de la page ({adresse.get('libelle_source')}).",
            action="Répète l'adresse dans un balisage LocalBusiness en JSON-LD. Lue dans du texte libre, elle dépend de la mise en page ; lue en JSON-LD, elle ne dépend de rien.",
            severite='moyenne',
        )

    coherence = nap.get('coherence')
    if not isinstance(coherence, dict) or 'severite' not in coherence:
        grille.ignore(cle, "Aucune source externe fournie : la cohérence entre citations n'a pas été comparée.")
        return
    ratios = {'aucune': 1.0, 'faible': 0.85, 'moyenne': 0.5, 'elevee': 0.25, 'critique': 0.0}
    severite = coherence.get('severite', 'aucune')
    grille.verifie(
        cle, 'nap_coherent', 6, ratios.get(severite, 0.5),
        constat="Le NAP est identique sur toutes les sources comparées.",
        probleme=coherence.get('resume') or "Le NAP diverge entre les sources comparées.",
        action="Corrige d'abord la source la plus consultée (la fiche Google), puis les annuaires, avec un copier-coller de la même écriture. Google recoupe les mentions : deux écritures créent deux entreprises à ses yeux.",
        severite=severite if severite != 'aucune' else 'faible',
    )


def _dim_schema(grille, signals) -> None:
    cle = 'schema_local'
    schema = [bloc for bloc in (signals.get('schema') or []) if isinstance(bloc, dict)]
    locaux = []
    for bloc in schema:
        brut = bloc.get('@type')
        types = brut if isinstance(brut, list) else [brut]
        plats = {_plat(t).replace(' ', '') for t in types if isinstance(t, str)}
        if plats & _TYPES_LOCAUX:
            locaux.append(bloc)

    grille.verifie(
        cle, 'schema_localbusiness', 5, bool(locaux),
        constat=f"{len(locaux)} entité(s) LocalBusiness dans le balisage.",
        probleme="Aucun balisage LocalBusiness sur la page.",
        action="Ajoute un bloc JSON-LD LocalBusiness (ou le sous-type de ton métier) avec name, address, telephone, openingHours et l'URL de la fiche Google dans sameAs.",
        severite='elevee',
    )
    if not locaux:
        grille.ignore(cle, "Champs du balisage local non évalués : aucune entité à lire.")
        grille.ignore(cle, "Coordonnées et horaires du balisage non évalués : aucune entité à lire.")
        return

    bloc = locaux[0]
    presents = sum(1 for champ in ('name', 'address', 'telephone') if bloc.get(champ))
    grille.verifie(
        cle, 'schema_champs', 3, presents / 3,
        constat="Le balisage local porte le nom, l'adresse et le téléphone.",
        probleme="Le balisage LocalBusiness est incomplet : "
                 + ', '.join(champ for champ in ('name', 'address', 'telephone')
                             if not bloc.get(champ)) + '.',
        action="Complète name, address (en PostalAddress) et telephone. Un balisage amputé de l'adresse ne sert à rien : c'est l'adresse qui rattache l'entité à un lieu.",
        severite='moyenne',
    )
    extras = sum(1 for champ in ('geo', 'openingHours', 'openingHoursSpecification',
                                 'sameAs', 'priceRange') if bloc.get(champ))
    grille.verifie(
        cle, 'schema_details', 2,
        1.0 if extras >= 2 else 0.5 if extras == 1 else 0.0,
        constat="Le balisage porte aussi les horaires, la géolocalisation ou les profils liés.",
        probleme="Le balisage local se limite au minimum : ni horaires, ni geo, ni sameAs.",
        action="Ajoute openingHoursSpecification, geo et sameAs vers la fiche Google et les réseaux. Ce sont les champs qui confirment que l'entité du site et celle de la fiche sont la même.",
        severite='faible',
    )


def _dim_autorite(grille, signals) -> None:
    cle = 'autorite_locale'
    liens = signals.get('links')
    internes = (liens.get('internal') or []) if isinstance(liens, dict) else []
    externes = (liens.get('external') or []) if isinstance(liens, dict) else []

    if not isinstance(liens, dict):
        grille.ignore(cle, "Liens de la page non lus : les pages locales n'ont pas été comptées.")
        grille.ignore(cle, "Liens de la page non lus : les liens vers le milieu local n'ont pas été comptés.")
    else:
        locales = 0
        for lien in internes:
            if not isinstance(lien, dict):
                continue
            cible = _plat(str(lien.get('href') or '')).replace('-', ' ')
            ancre = _plat(str(lien.get('text') or ''))
            if _RE_VILLE.search(cible) or _RE_REGION.search(cible) \
                    or _RE_VILLE.search(ancre) or _RE_REGION.search(ancre):
                locales += 1
        grille.verifie(
            cle, 'pages_locales', 4,
            1.0 if locales >= 3 else 0.5 if locales >= 1 else 0.0,
            constat=f"{locales} lien(s) interne(s) vers des pages de ville ou de région.",
            probleme="Aucun lien interne vers une page de ville ou de région.",
            action="Crée une page par ville réellement desservie, avec un contenu propre à chacune, et relie-les depuis le menu ou le pied de page. Une page par ville clonée mot pour mot ne classe pas : c'est du contenu dupliqué.",
            severite='moyenne',
        )

        milieu = 0
        for lien in externes:
            if not isinstance(lien, dict):
                continue
            cible = _plat(str(lien.get('href') or ''))
            if '.qc.ca' in cible or 'chambre' in cible or 'ville.' in cible \
                    or 'municipalite' in cible or 'tourisme' in cible:
                milieu += 1
        grille.verifie(
            cle, 'liens_milieu', 3, min(1.0, milieu / 2),
            constat=f"{milieu} lien(s) vers des organisations locales.",
            probleme="Aucun lien vers une organisation locale (chambre de commerce, municipalité, association du secteur).",
            action="Fais-toi lister par la chambre de commerce, l'association de ton métier et les répertoires régionaux, puis lie-les depuis le site. Ces liens locaux valent davantage qu'un annuaire national pour une recherche de proximité.",
            severite='faible',
        )

    corps = _texte_de(signals.get('text'))
    if not corps:
        grille.ignore(cle, "Aucun texte visible : les mentions du territoire n'ont pas été comptées.")
        return
    lieux = _lieux(corps)
    distincts = len(lieux['noms'])
    grille.verifie(
        cle, 'territoire', 3,
        1.0 if distincts >= 3 else 0.5 if distincts == 2 else 0.0,
        constat=f"Le contenu nomme {distincts} lieux distincts.",
        probleme="Le contenu nomme moins de trois lieux distincts : le territoire desservi reste flou.",
        action="Nomme les villes et les secteurs voisins que tu desservais vraiment cette année. Un rayon d'action explicite est ce qui te fait apparaître dans les recherches faites depuis la ville d'à côté.",
        severite='faible',
    )


def score_local_seo(signals: dict, *, nap=None, gbp=None, reviews=None) -> dict:
    """Score a local business on the six weighted dimensions of the grid.

    Args:
        signals: exactly the output of `html_parse.extract_seo_signals`.
        nap: the output of `extract_nap`, optionally carrying a 'coherence' key
            holding the output of `compare_nap`.
        gbp: what is known of the Google listing: 'revendiquee', 'categorie',
            'description', 'horaires', 'photos', 'derniere_publication',
            'site_web'. Absent keys are not scored.
        reviews: 'total', 'moyenne', 'taux_reponse' (or 'repondus') and
            'dernier'. Absent keys are not scored.

    Returns:
        {
          'score': 0-100, or None when nothing at all could be measured,
          'dimensions': {cle: {'libelle', 'poids', 'score', 'max', 'note',
                               'applicable', 'statut', 'constats', 'problemes',
                               'verifications', 'non_mesure'}},
          'recommandations': sorted by recoverable points,
          'couverture': how many of the 100 points were measurable,
          'dimensions_non_mesurees': [cle, ...],
        }

    `score` is the ratio of earned points to measurable points. A dimension
    nobody could look at leaves the denominator instead of scoring zero, so a
    site audited without its Google listing is not punished for the audit's own
    blind spot; `couverture` is what says whether the number deserves to be
    shown at all.
    """
    donnees = signals if isinstance(signals, dict) else {}
    grille = _Grille()
    _dim_fiche(grille, gbp)
    _dim_avis(grille, reviews)
    _dim_page(grille, donnees, nap)
    _dim_nap(grille, nap)
    _dim_schema(grille, donnees)
    _dim_autorite(grille, donnees)
    return grille.resultat()


# ---------------------------------------------------------------------------
# Public: which trade the page belongs to
# ---------------------------------------------------------------------------

def _motif(termes) -> re.Pattern:
    """One alternation over the terms, plural tolerated, hyphens not crossed."""
    morceaux = [
        r'\s+'.join(re.escape(mot) for mot in terme.split())
        for terme in termes
    ]
    return re.compile(r"(?<![\w-])(?:" + '|'.join(morceaux) + r")s?(?![\w-])")


_MOTIFS_VERTICALES = {
    cle: (_motif(forts), _motif(faibles))
    for cle, _, _, forts, faibles in VERTICALES
}

_POIDS_FORT = 3
_POIDS_FAIBLE = 1

# One term repeated in a menu must not outweigh three different terms, and the
# supporting vocabulary must never decide on its own: a construction page and a
# retail page both say "prix" and "commande".
_MAX_OCCURRENCES = 3
_PLAFOND_FAIBLES = 4


def _compte(motif, plat) -> list:
    trouves: dict[str, int] = {}
    for match in motif.finditer(plat):
        terme = ' '.join(match.group(0).split())
        trouves[terme] = trouves.get(terme, 0) + 1
    return [
        {'terme': terme, 'occurrences': nombre}
        for terme, nombre in sorted(trouves.items(), key=lambda item: -item[1])
    ]


def detect_vertical(text: str) -> dict:
    """Identify the trade a page belongs to, and say what decided it.

    Args:
        text: the visible text of the page. `extract_seo_signals(html)['text']`
            is the intended input, but a title plus a H1 works too.

    Returns:
        {
          'verticale': the key, or None when nothing matched,
          'libelle', 'type_schema': the French label and the schema.org type
              to declare for that trade,
          'score', 'confiance': how much decided it, and how safely,
          'signaux': the terms that decided, strongest first,
          'candidats': every trade that scored, best first,
        }

    Vocabulary decides, never a single word: a page has to carry a term of the
    trade nobody else writes before the supporting words are allowed to count,
    which is what keeps "prix", "commande" and "rendez-vous" from ranking every
    page as retail.
    """
    plat = _plat(text)
    candidats = []
    for cle, libelle, type_schema, _, _ in VERTICALES:
        motif_fort, motif_faible = _MOTIFS_VERTICALES[cle]
        forts = _compte(motif_fort, plat)
        faibles = _compte(motif_faible, plat)

        score_fort = sum(
            min(item['occurrences'], _MAX_OCCURRENCES) * _POIDS_FORT for item in forts
        )
        score_faible = min(
            _PLAFOND_FAIBLES,
            sum(min(item['occurrences'], _MAX_OCCURRENCES) * _POIDS_FAIBLE
                for item in faibles),
        )
        if not score_fort and not score_faible:
            continue

        signaux = (
            [dict(item, poids=_POIDS_FORT, force='fort') for item in forts]
            + [dict(item, poids=_POIDS_FAIBLE, force='faible') for item in faibles]
        )
        candidats.append({
            'cle': cle,
            'libelle': libelle,
            'type_schema': type_schema,
            'score': score_fort + score_faible,
            'score_fort': score_fort,
            'signaux': signaux[:12],
        })

    candidats.sort(key=lambda item: (-item['score'], -item['score_fort'], item['cle']))
    if not candidats or not candidats[0]['score']:
        return {
            'verticale': None,
            'libelle': None,
            'type_schema': None,
            'score': 0,
            'confiance': 'aucune',
            'signaux': [],
            'candidats': [],
        }

    gagnant = candidats[0]
    second = candidats[1]['score'] if len(candidats) > 1 else 0
    if gagnant['score_fort'] >= 6 and gagnant['score'] >= 2 * second:
        confiance = 'elevee'
    elif gagnant['score_fort'] >= 3:
        confiance = 'moyenne'
    else:
        confiance = 'faible'

    return {
        'verticale': gagnant['cle'],
        'libelle': gagnant['libelle'],
        'type_schema': gagnant['type_schema'],
        'score': gagnant['score'],
        'confiance': confiance,
        'signaux': gagnant['signaux'],
        'candidats': candidats,
    }
