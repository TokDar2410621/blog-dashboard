"""Falsifiability contract for the SEO recommendations Gridar emits.

Porte depuis claude-seo v2.2.4 `skills/seo/references/thinking-framework.md`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream is a ten-principle method an operator reads and applies by hand; the
two disciplines a client can actually check became code, ACCEPT ("every
recommendation gets a how would we know this failed line") and GROW ("define
one or two leading indicators"), while the rest stays in the prompt. The delay
table is added rather than ported: upstream names no horizon, and a failure
test with no deadline can never be run, so each recommendation type carries the
window after which silence counts as a refutation, measured on tools a Quebec
SMB already owns. Upstream's prose warning about recommending 30 location pages
to a two-person shop becomes arithmetic here, against team hours; the other
half of that question, whether the volume itself looks like a doorway set to
Google, already lives in `quality_gates.check_location_volume`.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

__all__ = [
    'RECOMMENDATION_SYSTEM_PROMPT',
    'CHAMPS_OBLIGATOIRES',
    'TYPES_RECOMMANDATION',
    'INDICATEURS_PAR_TYPE',
    'SCALE_SANITY',
    'deviner_type',
    'validate_recommendation',
    'enrich_recommendation',
    'check_scale_sanity',
]


# The four fields that turn a sentence into a claim someone can refute. The
# model is asked for exactly these; anything else in a recommendation is ours.
CHAMPS_OBLIGATOIRES = ('observation', 'dependances', 'test_echec',
                       'indicateur_avance')

# Findings come out of validate_recommendation in this order.
_RANG_NIVEAU = {'erreur': 0, 'avertissement': 1}


# ---------------------------------------------------------------------------
# Recommendation types: leading indicator, day-zero proof, observation window
# ---------------------------------------------------------------------------
#
# `delai_min_jours` / `delai_max_jours` are the window after which no movement
# refutes the recommendation. They are properties of the measuring tool, not
# opinions: Core Web Vitals field data is a rolling 28-day average, so judging
# a speed fix at day 10 measures the old page. `verification_immediate` is the
# separate day-zero check that the change actually shipped, which is what
# separates "the fix did nothing" from "the fix was never deployed".
# `mots_cles` are folded, accent-free, and matched on word boundaries.

INDICATEURS_PAR_TYPE = {
    'indexation': {
        'libelle': "Indexation et exploration",
        'indicateur': (
            "le nombre d'URL indexées dans le rapport Pages de la Search Console"
        ),
        'verification_immediate': (
            "l'inspection d'URL de la Search Console sur une page témoin, qui doit "
            "répondre « L'URL est sur Google »"
        ),
        'delai_min_jours': 3,
        'delai_max_jours': 21,
        'unite_defaut': 'page',
        'mots_cles': (
            'indexation', 'indexer', 'indexee', 'indexees', 'noindex',
            'robots.txt', 'meta robots', 'canonique', 'canonical', 'sitemap',
            'exploration', 'crawl', 'budget de crawl', 'redirection',
            'erreur 404', 'pagination',
        ),
    },
    'rendu_js': {
        'libelle': "Contenu dépendant du JavaScript",
        'indicateur': (
            "la présence du texte principal dans le HTML servi, vue par "
            "l'inspection d'URL (onglet HTML testé)"
        ),
        'verification_immediate': (
            "afficher le code source de la page sans exécuter le JavaScript et y "
            "retrouver le texte principal"
        ),
        'delai_min_jours': 7,
        'delai_max_jours': 28,
        'unite_defaut': 'page',
        'mots_cles': (
            'javascript', 'js', 'spa', 'react', 'vue', 'angular', 'hydratation',
            'rendu cote client', 'rendu serveur', 'ssr', 'pre-rendu',
        ),
    },
    'vitesse': {
        'libelle': "Vitesse et Signaux web essentiels",
        'indicateur': (
            "le LCP et l'INP au 75e centile dans le rapport Signaux web "
            "essentiels (données terrain CrUX, moyenne glissante sur 28 jours)"
        ),
        'verification_immediate': (
            "un test PageSpeed Insights sur la page corrigée, qui doit montrer le "
            "gain en laboratoire dès le jour même"
        ),
        'delai_min_jours': 28,
        'delai_max_jours': 56,
        'unite_defaut': 'page',
        'mots_cles': (
            'lcp', 'inp', 'cls', 'core web vitals', 'signaux web essentiels',
            'vitesse', 'temps de chargement', 'poids des images', 'compression',
            'lazy loading', 'cache', 'pagespeed', 'webp',
        ),
    },
    'balises_titres': {
        'libelle': "Titres et métadonnées",
        'indicateur': (
            "le taux de clic (CTR) de l'URL dans la Search Console, à volume "
            "d'impressions comparable"
        ),
        'verification_immediate': (
            "recharger la page et lire la nouvelle balise dans le code source"
        ),
        'delai_min_jours': 7,
        'delai_max_jours': 28,
        'unite_defaut': 'balise',
        'mots_cles': (
            'balise titre', 'balise title', 'title', 'meta description',
            'metadescription', 'meta-description', 'h1', 'titre de la page',
            'titre h1', 'sous-titres',
        ),
    },
    'donnees_structurees': {
        'libelle': "Données structurées",
        'indicateur': (
            "le nombre d'éléments valides dans les rapports de résultats enrichis "
            "de la Search Console"
        ),
        'verification_immediate': (
            "le test des résultats enrichis de Google sur l'URL, sans erreur ni "
            "avertissement bloquant"
        ),
        'delai_min_jours': 3,
        'delai_max_jours': 28,
        'unite_defaut': 'balise',
        'mots_cles': (
            'schema', 'schema.org', 'json-ld', 'jsonld', 'donnees structurees',
            'balisage', 'resultats enrichis', 'rich results', 'localbusiness',
            'faqpage', 'breadcrumb', 'fil d\'ariane',
        ),
    },
    'contenu_nouveau': {
        'libelle': "Nouveau contenu",
        'indicateur': (
            "les impressions de la nouvelle URL sur ses requêtes cibles dans la "
            "Search Console"
        ),
        'verification_immediate': (
            "la page est en ligne, accessible sans mot de passe et reliée depuis "
            "au moins un menu ou une page existante"
        ),
        'delai_min_jours': 28,
        'delai_max_jours': 112,
        'unite_defaut': 'article',
        'mots_cles': (
            'creer une page', 'creer un article', 'creer des pages',
            'nouvelle page', 'nouvelles pages', 'nouvel article',
            'nouveaux articles', 'rediger', 'publier un', 'publier des',
            'ajouter une page', 'nouveau contenu',
        ),
    },
    'contenu_refonte': {
        'libelle': "Refonte de contenu existant",
        'indicateur': (
            "la position moyenne et les impressions de l'URL sur ses requêtes "
            "cibles dans la Search Console"
        ),
        'verification_immediate': (
            "la nouvelle version est en ligne et la date de mise à jour est "
            "visible sur la page"
        ),
        'delai_min_jours': 14,
        'delai_max_jours': 56,
        'unite_defaut': 'article',
        'mots_cles': (
            'reecrire', 'reecriture', 'enrichir', 'etoffer', 'approfondir',
            'mettre a jour', 'mise a jour', 'rafraichir', 'actualiser',
            'contenu mince', 'completer la page', 'ajouter une section',
        ),
    },
    'consolidation': {
        'libelle': "Consolidation de pages concurrentes",
        'indicateur': (
            "le nombre d'URL du site qui se partagent la même requête dans la "
            "Search Console, puis les clics de l'URL survivante"
        ),
        'verification_immediate': (
            "les anciennes URL répondent par une redirection 301 vers l'URL "
            "conservée, sans chaîne de redirections"
        ),
        'delai_min_jours': 21,
        'delai_max_jours': 84,
        'unite_defaut': 'page',
        'mots_cles': (
            'fusionner', 'consolider', 'consolidation', 'cannibalisation',
            'regrouper', 'doublon', 'contenu duplique', 'pages concurrentes',
            'desindexer',
        ),
    },
    'maillage_interne': {
        'libelle': "Maillage interne",
        'indicateur': (
            "le nombre de liens internes vers la page cible dans le rapport Liens "
            "de la Search Console, puis ses impressions"
        ),
        'verification_immediate': (
            "les liens sont présents dans le HTML servi, en <a href> cliquable, "
            "avec une ancre descriptive"
        ),
        'delai_min_jours': 14,
        'delai_max_jours': 56,
        'unite_defaut': 'lien_interne',
        'mots_cles': (
            'maillage', 'lien interne', 'liens internes', 'ancre',
            'ancres de liens', 'page orpheline', 'pages orphelines', 'silo',
            'navigation interne', 'profondeur de clic',
        ),
    },
    'seo_local': {
        'libelle': "SEO local",
        'indicateur': (
            "les vues et les actions (appels, itinéraires, clics vers le site) de "
            "la fiche Google Business"
        ),
        'verification_immediate': (
            "la fiche Google Business affiche l'information corrigée et le NAP est "
            "identique sur le site"
        ),
        'delai_min_jours': 14,
        'delai_max_jours': 56,
        'unite_defaut': 'page_localite',
        'mots_cles': (
            'fiche google', 'google business', 'gbp', 'nap', 'seo local',
            'local', 'locale', 'locales', 'localite', 'localites', 'ville', 'villes',
            'quartier', 'avis google', 'google maps', 'horaires',
        ),
    },
    'notoriete': {
        'libelle': "Notoriété et mentions de marque",
        'indicateur': (
            "le nombre de domaines distincts qui citent la marque, mentions "
            "comprises et pas seulement les liens"
        ),
        'verification_immediate': (
            "la mention ou le lien est publié, public et trouvable par une "
            "recherche sur le nom de la marque"
        ),
        'delai_min_jours': 28,
        'delai_max_jours': 112,
        'unite_defaut': 'mention',
        'mots_cles': (
            'mention', 'mentions', 'mentions de marque', 'notoriete',
            'relations publiques', 'backlink', 'backlinks', 'lien entrant',
            'liens entrants', 'netlinking', 'reddit', 'youtube', 'presse',
            'annuaire', 'annuaires', 'partenariat',
        ),
    },
    'visibilite_ia': {
        'libelle': "Visibilité dans les réponses IA",
        'indicateur': (
            "le taux de citation de la marque sur un panier de questions rejouées "
            "chaque mois dans ChatGPT, Perplexity et les aperçus IA de Google"
        ),
        'verification_immediate': (
            "la réponse à la question cible existe sur la page, en clair, dans les "
            "premières lignes de la section"
        ),
        'delai_min_jours': 14,
        'delai_max_jours': 56,
        'unite_defaut': 'article',
        'mots_cles': (
            'chatgpt', 'perplexity', 'ai overview', 'ai overviews', 'apercu ia',
            'apercus ia', 'reponses ia', 'citation ia', 'citations ia', 'llm',
            'geo', 'aeo', 'moteur de reponse', 'intelligence artificielle',
        ),
    },
    'experience_serp': {
        'libelle': "Attractivité dans les résultats",
        'indicateur': (
            "le taux de clic (CTR) de l'URL dans la Search Console, à position "
            "moyenne comparable"
        ),
        'verification_immediate': (
            "la nouvelle formulation est en ligne et Google la reprend dans son "
            "extrait après le prochain passage"
        ),
        'delai_min_jours': 14,
        'delai_max_jours': 42,
        'unite_defaut': 'page',
        'mots_cles': (
            'ctr', 'taux de clic', 'extrait', 'extraits', 'snippet', 'sxo',
            'serp', 'attractivite', 'position zero',
        ),
    },
    'autre': {
        'libelle': "Autre",
        'indicateur': (
            "les impressions et les clics des URL touchées dans la Search Console"
        ),
        'verification_immediate': (
            "le changement est visible en ligne sur l'URL concernée"
        ),
        'delai_min_jours': 14,
        'delai_max_jours': 56,
        'unite_defaut': 'page',
        'mots_cles': (),
    },
}

TYPES_RECOMMANDATION = tuple(INDICATEURS_PAR_TYPE)

_TYPE_DEFAUT = 'autre'


# ---------------------------------------------------------------------------
# Operator capacity
# ---------------------------------------------------------------------------
#
# Hours are per finished unit with Gridar drafting: they cover gathering the
# real local material, validating the draft, publishing and checking. A
# two-person shop does not put two full-time people on SEO, which is why the
# capacity is expressed per person and per week rather than as headcount.

SCALE_SANITY = {
    'heures_par_personne_par_semaine': 4.0,
    'horizon_semaines': 12,
    # Above this share of the available hours the plan crowds out everything
    # else; above 100 % it is arithmetic fiction.
    'seuil_avertissement': 0.6,
    'seuil_blocage': 1.0,
    'cout_heures': {
        'page_localite': 4.0,
        'page_service': 5.0,
        'page': 4.0,
        'article': 4.0,
        'fiche_produit': 1.0,
        'lien_interne': 0.25,
        'balise': 0.25,
        'lien_entrant': 4.0,
        'mention': 3.0,
        'video': 8.0,
        'avis': 0.5,
        'traduction': 3.0,
    },
}

# Ordered longest-first: the alternation is tried left to right, so "pages de
# localite" has to sit before the bare "pages" or every location page would be
# priced as a generic page.
_UNITES = (
    (r'pages? de localites?', 'page_localite'),
    (r'pages? de villes?', 'page_localite'),
    (r'pages? de services?', 'page_service'),
    (r"pages? d'atterrissage", 'page_service'),
    (r'landings?', 'page_service'),
    (r'pages? produits?', 'fiche_produit'),
    (r'fiches? produits?', 'fiche_produit'),
    (r'etudes? de cas', 'article'),
    (r'articles?', 'article'),
    (r'billets?', 'article'),
    (r'temoignages?', 'avis'),
    (r'avis', 'avis'),
    (r'liens? internes?', 'lien_interne'),
    (r'liens? entrants?', 'lien_entrant'),
    (r'backlinks?', 'lien_entrant'),
    (r'mentions?', 'mention'),
    (r'meta ?descriptions?', 'balise'),
    (r'balises?', 'balise'),
    (r'titles?', 'balise'),
    (r'videos?', 'video'),
    (r'traductions?', 'traduction'),
    (r'pages?', 'page'),
)

# (singular, plural) shown to the client. The regex above matches accent-folded
# text, so printing the matched string back would put "localite" in a French
# report.
_LIBELLES_UNITE = {
    'page_localite': ('page de localité', 'pages de localité'),
    'page_service': ('page de service', 'pages de service'),
    'page': ('page', 'pages'),
    'article': ('article', 'articles'),
    'fiche_produit': ('fiche produit', 'fiches produits'),
    'lien_interne': ('lien interne', 'liens internes'),
    'balise': ('balise', 'balises'),
    'lien_entrant': ('lien entrant', 'liens entrants'),
    'mention': ('mention de marque', 'mentions de marque'),
    'video': ('vidéo', 'vidéos'),
    'avis': ('avis', 'avis'),
    'traduction': ('traduction', 'traductions'),
}

_QUANTITE_RE = re.compile(
    r'\b(\d{1,4})\s+(?:nouvelles?\s+|nouveaux\s+|autres\s+)?('
    + '|'.join(motif for motif, _ in _UNITES)
    + r')\b'
)


# ---------------------------------------------------------------------------
# Text heuristics
# ---------------------------------------------------------------------------

# An observation has to point at something seen on the site. Without one of
# these markers or a figure, the sentence is usually a best practice recited
# from memory rather than a finding.
_MARQUEURS_CONSTAT = (
    'aucun', 'aucune', 'absent', 'absente', 'manque', 'manquant', 'manquante',
    'present', 'presente', 'contient', 'affiche', 'renvoie', 'retourne',
    'pointe', 'charge', 'mesure', 'observe', 'constate', 'detecte', 'declare',
    'utilise', 'la page', 'les pages', 'le site', 'cette url', 'le serveur',
    'le html', 'le fichier', 'la fiche', 'le titre', 'la balise',
)

# A failure test states a result that would not happen if the hypothesis held.
# Presence of one of these is a positive signal, so a wide list is safe.
_MARQUEURS_ECHEC = (
    "n'a pas", "n'ont pas", 'ne bouge', 'ne bougent', 'ne change', 'ne changent',
    "n'augmente", "n'augmentent", 'ne progresse', 'ne progressent',
    'ne depasse', 'ne depassent', 'ne monte', 'ne montent', 'aucun', 'aucune',
    'pas de', 'sans', 'stagne', 'stagnent', 'reste', 'restent', 'moins de',
    'inferieur', 'inferieure', 'baisse', 'recule', 'reculent', 'zero',
    'toujours pas', 'echoue', 'identique', 'inchange', 'inchangee',
    'en dessous', 'sous le', 'sous les',
    # The other half of the phrasing: not a negation but an explicit verdict
    # ("l'hypothese est fausse", "la page est toujours exclue").
    'fausse', 'faux', 'invalide', 'invalidee', 'infirme', 'toujours', 'encore',
    'persiste', 'persistent', 'demeure', 'demeurent', 'echec',
)

_ECHEANCE_RE = re.compile(
    r'\b\d+\s*(?:jours?|semaines?|mois|trimestres?)\b'
    r'|\b\d{4}-\d{2}-\d{2}\b'
)

# Where the client goes to read the number. An indicator that names no source
# cannot be checked by the person paying for the recommendation.
_SOURCES_MESURE = (
    'search console', 'gsc', 'console de recherche', 'impressions', 'clics',
    'position', 'positions', 'ctr', 'taux de clic', 'crux', 'lcp', 'inp', 'cls',
    'pagespeed', 'signaux web essentiels', 'fiche google', 'google business',
    'appels', 'itineraires', 'formulaires', 'demandes de soumission',
    'citations', 'mentions', 'resultats enrichis', 'pages indexees',
    'urls indexees', "inspection d'url", 'analytics', 'ga4', 'sessions',
    'liens internes', 'domaines', 'avis',
)

# Business outcomes. They are the point, but they move after the SEO signal
# moves, so they cannot tell the client this month whether the bet is working.
_INDICATEURS_RETARDES = (
    "chiffre d'affaires", 'revenu', 'revenus', 'ventes', 'roi', 'rentabilite',
    'profit', 'profits', 'marge', 'clients signes', 'contrats signes',
    'retour sur investissement', 'notoriete de la marque',
)


def _fold(text) -> str:
    """Lowercase, drop accents, normalize the typographic apostrophe.

    Every keyword table below is written folded, so a page that spells
    "localité" and one that spells "localite" hit the same rule.
    """
    if not isinstance(text, str):
        text = '' if text is None else str(text)
    s = unicodedata.normalize('NFD', text.lower().replace('’', "'"))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def _texte(valeur) -> str:
    if valeur is None:
        return ''
    if not isinstance(valeur, str):
        valeur = str(valeur)
    return valeur.strip()


def _contient(folded: str, mots) -> bool:
    for mot in mots:
        if re.search(r'(?<![a-z0-9])' + re.escape(mot) + r'(?![a-z0-9])', folded):
            return True
    return False


def _similaire(a: str, b: str) -> float:
    return SequenceMatcher(None, _fold(a), _fold(b)).ratio()


def _libelle_delai(jours_min: int, jours_max: int) -> str:
    """Human window, in days below three weeks and in weeks above."""
    if jours_max <= 21:
        return f'{jours_min} à {jours_max} jours'
    semaines_min = max(1, round(jours_min / 7))
    semaines_max = max(semaines_min + 1, round(jours_max / 7))
    return f'{semaines_min} à {semaines_max} semaines'


def _libelle_unite(cle_cout: str, quantite: int, defaut: str = '') -> str:
    """French label for a counted unit, so nothing unaccented reaches the client.

    The unit is matched on accent-folded text, and that folded form is what a
    naive port would print back.
    """
    formes = _LIBELLES_UNITE.get(cle_cout)
    if not formes:
        return defaut or cle_cout.replace('_', ' ')
    return formes[0] if quantite == 1 else formes[1]


def deviner_type(texte: str) -> str:
    """Best-guess recommendation type from its wording.

    Scored rather than first-match: "créer 30 pages de localité" mentions both
    a creation verb and a local signal, and the local reading is the one that
    picks the right leading indicator. Ties fall to the earliest type in the
    table, and no keyword at all falls to 'autre'.
    """
    folded = _fold(texte)
    if not folded:
        return _TYPE_DEFAUT

    meilleur, score_max = _TYPE_DEFAUT, 0
    for cle, fiche in INDICATEURS_PAR_TYPE.items():
        score = sum(
            1 for mot in fiche['mots_cles']
            if re.search(r'(?<![a-z0-9])' + re.escape(mot) + r'(?![a-z0-9])', folded)
        )
        if score > score_max:
            meilleur, score_max = cle, score
    return meilleur


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_PROMPT = """\
Tu produis des recommandations SEO pour une PME du Québec. Elles seront lues \
par le propriétaire de l'entreprise, pas par un spécialiste, et quelqu'un ira \
vérifier dans quelques semaines si tu avais raison.

Une recommandation qu'on ne peut pas déclarer fausse est une opinion. Chaque \
recommandation que tu émets porte donc ces quatre champs, sans exception.

1. observation
   Le fait constaté sur le site qui justifie la recommandation, avec son \
chiffre, son URL ou sa citation. Ce n'est pas une reformulation de l'action. \
Si tu ne peux nommer aucun fait observé, tu n'as pas une recommandation, tu as \
une habitude.

2. dependances
   Ce qui doit être vrai ou fait avant que cette recommandation puisse produire \
un effet, sous forme de liste. Une liste vide est une réponse valable, mais \
c'est une affirmation : tu déclares que rien ne bloque. Une page qui n'est pas \
indexable fait attendre tout le travail de contenu qui en dépend.

3. test_echec
   La phrase qui dit comment on saurait que tu as eu tort. Elle nomme un \
indicateur, un seuil et une échéance. Exemple : « Si les impressions de cette \
URL n'ont pas augmenté après 8 semaines alors que l'inspection d'URL confirme \
qu'elle est indexée, l'hypothèse est fausse. »

4. indicateur_avance
   Ce que le client surveille en attendant, dans un outil qu'il possède déjà \
(Search Console, Signaux web essentiels, fiche Google Business). Un indicateur \
avancé bouge avant le résultat commercial. Le chiffre d'affaires et les ventes \
ne sont pas des indicateurs avancés.

Règles de fond :
- Une seule idée par recommandation. Si deux actions ont deux tests d'échec \
différents, ce sont deux recommandations.
- La contrainte qui bloque tout le reste passe en premier, même si elle est \
moins intéressante que les autres.
- Si les résultats de recherche de la requête visée contredisent ta \
recommandation, ce sont eux qui gagnent, sauf si tu peux expliquer pourquoi ce \
site est l'exception.
- Ne recommande jamais un volume que l'équipe ne peut pas produire. Trente \
pages de localité pour une entreprise de deux personnes, c'est une \
recommandation qui ne sera jamais exécutée.
- Si le client a déjà essayé une approche sans résultat, ne la répète pas sans \
dire ce qui change cette fois.
- Écris en français du Québec, à la deuxième personne, sans jargon inutile.

Format de sortie : un tableau JSON, rien avant, rien après.
[
  {
    "action": "ce qu'il faut faire, à l'impératif",
    "type": "une valeur de la liste ci-dessous",
    "observation": "le fait constaté qui justifie l'action",
    "dependances": ["ce qui doit être fait avant"],
    "test_echec": "ce qui prouverait que la recommandation était fausse",
    "indicateur_avance": "ce qu'on surveille en attendant, et où le lire",
    "quantite": null,
    "unite": null
  }
]

Valeurs permises pour "type" : __TYPES__.

"quantite" et "unite" ne se remplissent que si l'action porte sur un nombre \
d'éléments, par exemple 12 pour "pages de localité" ou 30 pour "liens \
internes". Sinon, laisse les deux à null.\
"""

RECOMMENDATION_SYSTEM_PROMPT = _PROMPT.replace(
    '__TYPES__', ', '.join(TYPES_RECOMMANDATION)
)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _finding(niveau: str, champ: str, code: str, message: str,
             correction: str) -> dict:
    return {
        'niveau': niveau,
        'champ': champ,
        'code': code,
        'message': message,
        'correction': correction,
    }


def validate_recommendation(reco: dict) -> list[dict]:
    """List what stops this recommendation from being falsifiable.

    Each finding is {niveau, champ, code, message, correction}, 'erreur'
    before 'avertissement'. An empty list means the four fields are present
    and usable; it says nothing about whether the recommendation is right,
    which only the failure test can settle later.
    """
    if not isinstance(reco, dict):
        return [_finding(
            'erreur', '', 'structure_invalide',
            "La recommandation n'est pas un objet exploitable.",
            "Fournir un objet JSON avec les champs action, observation, "
            "dependances, test_echec et indicateur_avance.",
        )]

    problemes = []
    action = _texte(reco.get('action'))

    if not action:
        problemes.append(_finding(
            'erreur', 'action', 'action_manquante',
            "Aucune action : on ne sait pas quoi faire.",
            "Écrire l'action à l'impératif, en une phrase.",
        ))

    problemes.extend(_valider_observation(reco, action))
    problemes.extend(_valider_dependances(reco, action))
    problemes.extend(_valider_test_echec(reco))
    problemes.extend(_valider_indicateur(reco))

    type_ = _texte(reco.get('type'))
    if not type_:
        problemes.append(_finding(
            'avertissement', 'type', 'type_absent',
            "Aucun type de recommandation : l'indicateur avancé et le délai "
            "d'observation seront déduits du texte.",
            "Renseigner « type » avec une des valeurs permises : "
            + ', '.join(TYPES_RECOMMANDATION) + '.',
        ))
    elif type_ not in INDICATEURS_PAR_TYPE:
        problemes.append(_finding(
            'avertissement', 'type', 'type_inconnu',
            f"Type « {type_} » inconnu, le délai d'observation retombera sur "
            "une valeur générique.",
            "Utiliser une des valeurs permises : "
            + ', '.join(TYPES_RECOMMANDATION) + '.',
        ))

    problemes.sort(key=lambda p: _RANG_NIVEAU.get(p['niveau'], 9))
    return problemes


def _valider_observation(reco: dict, action: str) -> list[dict]:
    observation = _texte(reco.get('observation'))
    if not observation:
        return [_finding(
            'erreur', 'observation', 'observation_manquante',
            "Aucune observation : rien ne prouve que le problème existe sur ce "
            "site.",
            "Nommer le fait constaté, avec son chiffre, son URL ou sa citation.",
        )]

    problemes = []
    if action and _similaire(observation, action) >= 0.75:
        problemes.append(_finding(
            'erreur', 'observation', 'observation_reformule_action',
            "L'observation répète l'action au lieu de la justifier.",
            "Remplacer par ce qui a été mesuré sur le site avant de proposer "
            "quoi que ce soit.",
        ))
    elif len(observation) < 40:
        problemes.append(_finding(
            'avertissement', 'observation', 'observation_vague',
            "Observation trop courte pour porter un constat vérifiable.",
            "Ajouter le chiffre, l'URL ou l'extrait exact qui a été relevé.",
        ))

    folded = _fold(observation)
    if not re.search(r'\d', folded) and not _contient(folded, _MARQUEURS_CONSTAT):
        problemes.append(_finding(
            'avertissement', 'observation', 'observation_sans_constat',
            "L'observation ne pointe rien de mesuré sur ce site : elle ressemble "
            "à une bonne pratique récitée.",
            "Citer ce qui a été vu sur la page ou dans les données, avec un "
            "chiffre quand il y en a un.",
        ))
    return problemes


def _valider_dependances(reco: dict, action: str) -> list[dict]:
    if 'dependances' not in reco:
        # An empty list is a claim ("nothing blocks this"); an absent key is
        # only silence, and silence is what we are trying to remove.
        return [_finding(
            'erreur', 'dependances', 'dependances_absentes',
            "Le champ « dependances » manque : on ne sait pas si quelque chose "
            "doit être fait avant.",
            "Lister ce qui doit être vrai avant, ou déclarer une liste vide si "
            "rien ne bloque.",
        )]

    valeur = reco.get('dependances')
    if not isinstance(valeur, (list, tuple)):
        return [_finding(
            'erreur', 'dependances', 'dependances_format',
            "« dependances » doit être une liste, même vide.",
            "Fournir un tableau de courtes phrases, une par dépendance.",
        )]

    problemes = []
    for element in valeur:
        if not _texte(element):
            problemes.append(_finding(
                'avertissement', 'dependances', 'dependance_vide',
                "Une dépendance est vide et n'apprend rien.",
                "La retirer ou la formuler.",
            ))
            continue
        if action and _similaire(element, action) >= 0.8:
            problemes.append(_finding(
                'avertissement', 'dependances', 'dependance_circulaire',
                "Une dépendance répète l'action elle-même.",
                "Nommer ce qui doit être fait par quelqu'un d'autre ou avant, "
                "pas l'action en cours.",
            ))
    return problemes


def _valider_test_echec(reco: dict) -> list[dict]:
    test = _texte(reco.get('test_echec'))
    if not test:
        return [_finding(
            'erreur', 'test_echec', 'test_echec_manquant',
            "Aucun test d'échec : la recommandation est une opinion, personne ne "
            "pourra dire qu'elle a raté.",
            "Écrire ce qui, dans les chiffres, prouverait que l'hypothèse était "
            "fausse.",
        )]

    problemes = []
    folded = _fold(test)
    if not _contient(folded, _MARQUEURS_ECHEC):
        problemes.append(_finding(
            'erreur', 'test_echec', 'test_echec_non_falsifiable',
            "Le test d'échec ne décrit aucun résultat qui invaliderait la "
            "recommandation.",
            "Le formuler à la négative : « Si tel indicateur n'a pas bougé "
            "après tel délai, l'hypothèse est fausse. »",
        ))
    if not _ECHEANCE_RE.search(folded):
        problemes.append(_finding(
            'avertissement', 'test_echec', 'test_echec_sans_echeance',
            "Le test d'échec n'a pas d'échéance : sans date, on peut toujours "
            "dire qu'il faut attendre encore.",
            "Ajouter un délai chiffré, par exemple « après 8 semaines ».",
        ))
    return problemes


def _valider_indicateur(reco: dict) -> list[dict]:
    indicateur = _texte(reco.get('indicateur_avance'))
    if not indicateur:
        return [_finding(
            'erreur', 'indicateur_avance', 'indicateur_manquant',
            "Aucun indicateur avancé : le client n'a rien à surveiller entre "
            "aujourd'hui et le verdict.",
            "Nommer un chiffre qui bouge tôt, et l'outil où le lire.",
        )]

    problemes = []
    folded = _fold(indicateur)
    if _contient(folded, _INDICATEURS_RETARDES):
        problemes.append(_finding(
            'avertissement', 'indicateur_avance', 'indicateur_retarde',
            "Cet indicateur mesure le résultat commercial, qui bouge après le "
            "signal SEO : il ne dira rien avant plusieurs mois.",
            "Choisir un signal qui bouge en premier : impressions, positions, "
            "pages indexées, vues de la fiche Google.",
        ))
    if not _contient(folded, _SOURCES_MESURE):
        problemes.append(_finding(
            'avertissement', 'indicateur_avance', 'indicateur_sans_source',
            "L'indicateur ne dit pas où se lit le chiffre.",
            "Nommer l'outil : Search Console, Signaux web essentiels, fiche "
            "Google Business.",
        ))
    return problemes


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------

def _gabarit_test_echec(fiche: dict) -> str:
    delai = _libelle_delai(fiche['delai_min_jours'], fiche['delai_max_jours'])
    return (
        f"Si {fiche['indicateur']} n'a pas bougé après {delai}, alors que la "
        f"vérification du jour même ({fiche['verification_immediate']}) confirme "
        "que le changement est bien en ligne, l'hypothèse est fausse et la cause "
        "est ailleurs."
    )


def enrich_recommendation(reco: dict, context: dict = None) -> dict:
    """Fill in what the table can settle without asking the model again.

    Completes the type, the leading indicator, the day-zero check and the
    observation window, and writes a failure test from them when the model
    left it out. Nothing the model produced is overwritten, and the caller
    gets `champs_completes` so the interface can tell the two apart. The
    observation window always comes from the table: it is a property of the
    measuring tool, not a judgement call. `context` accepts taille_equipe,
    heures_par_semaine, horizon_semaines and deja_essaye.
    """
    sortie = dict(reco) if isinstance(reco, dict) else {}
    ctx = context if isinstance(context, dict) else {}
    completes = []
    avertissements = []

    type_ = _texte(sortie.get('type'))
    if type_ not in INDICATEURS_PAR_TYPE:
        type_ = deviner_type(
            f"{_texte(sortie.get('action'))} {_texte(sortie.get('observation'))}"
        )
        sortie['type'] = type_
        completes.append('type')
    fiche = INDICATEURS_PAR_TYPE[type_]
    sortie['type_libelle'] = fiche['libelle']

    if not _texte(sortie.get('indicateur_avance')):
        sortie['indicateur_avance'] = fiche['indicateur']
        completes.append('indicateur_avance')

    if not _texte(sortie.get('verification_immediate')):
        sortie['verification_immediate'] = fiche['verification_immediate']
        completes.append('verification_immediate')

    sortie['delai_observation_jours'] = [
        fiche['delai_min_jours'], fiche['delai_max_jours'],
    ]
    sortie['delai_observation'] = _libelle_delai(
        fiche['delai_min_jours'], fiche['delai_max_jours'],
    )
    completes.extend(['delai_observation_jours', 'delai_observation'])

    if not _texte(sortie.get('test_echec')):
        sortie['test_echec'] = _gabarit_test_echec(fiche)
        completes.append('test_echec')

    echelle = check_scale_sanity(sortie, ctx)
    sortie['echelle'] = echelle
    if echelle.get('applicable') and echelle.get('niveau') != 'ok':
        avertissements.append(echelle['message'])

    deja = ctx.get('deja_essaye') or []
    action = _texte(sortie.get('action'))
    if action and isinstance(deja, (list, tuple)):
        for tentative in deja:
            if _texte(tentative) and _similaire(action, tentative) >= 0.72:
                avertissements.append(
                    f"Le client a déjà essayé « {_texte(tentative)} » sans "
                    "résultat. Ne pas reproposer la même chose sans dire ce qui "
                    "change cette fois."
                )
                break

    sortie['champs_completes'] = completes
    sortie['avertissements'] = avertissements
    return sortie


# ---------------------------------------------------------------------------
# Operator capacity check
# ---------------------------------------------------------------------------

def _extraire_quantite(reco: dict) -> tuple:
    """(quantity, unit label, cost key) or (None, '', '') when there is none.

    Explicit fields win; otherwise the figure is read from the action, since a
    model asked for prose writes "créer 30 pages de localité" far more often
    than it fills a quantity field.
    """
    brut = reco.get('quantite')
    unite = _texte(reco.get('unite'))
    quantite = None
    if isinstance(brut, bool):
        brut = None
    if brut is not None:
        try:
            quantite = int(float(brut))
        except (TypeError, ValueError):
            quantite = None

    if quantite is not None and quantite > 0:
        cle = _cle_cout_pour_unite(unite)
        return quantite, unite or '', cle

    match = _QUANTITE_RE.search(_fold(reco.get('action')))
    if not match:
        return None, '', ''
    return int(match.group(1)), match.group(2), _cle_cout_pour_motif(match.group(2))


def _cle_cout_pour_motif(unite_folded: str) -> str:
    for motif, cle in _UNITES:
        if re.fullmatch(motif, unite_folded):
            return cle
    return ''


def _cle_cout_pour_unite(unite: str) -> str:
    folded = _fold(unite)
    if not folded:
        return ''
    cle = _cle_cout_pour_motif(folded)
    if cle:
        return cle
    for motif, candidat in _UNITES:
        if re.search(motif, folded):
            return candidat
    return ''


def check_scale_sanity(reco: dict, context: dict = None) -> dict:
    """Confront the size of a recommendation with the hours the team has.

    The upstream framework names this failure in prose, recommending 30
    location pages to a two-person shop, and leaves it to the operator's
    judgement. Here it is arithmetic: units times hours per unit against
    headcount times weekly SEO hours over the horizon. Returns
    {applicable, niveau, ...}; niveau is 'ok', 'avertissement' or 'blocage',
    and 'blocage' carries the volume that would fit instead.
    """
    ctx = context if isinstance(context, dict) else {}
    base = {
        'applicable': False,
        'niveau': 'ok',
        'raison': '',
        'message': '',
    }
    if not isinstance(reco, dict):
        base['raison'] = "Recommandation illisible."
        return base

    quantite, unite, cle_cout = _extraire_quantite(reco)
    if not quantite:
        base['raison'] = "Aucune quantité chiffrée dans la recommandation."
        return base

    if not cle_cout:
        type_ = _texte(reco.get('type'))
        fiche = INDICATEURS_PAR_TYPE.get(type_)
        cle_cout = fiche['unite_defaut'] if fiche else 'page'

    try:
        taille = int(ctx.get('taille_equipe'))
    except (TypeError, ValueError):
        taille = 0
    if taille <= 0:
        base['raison'] = "Taille de l'équipe inconnue."
        return base

    try:
        heures_semaine = float(
            ctx.get('heures_par_semaine')
            or SCALE_SANITY['heures_par_personne_par_semaine']
        )
    except (TypeError, ValueError):
        heures_semaine = SCALE_SANITY['heures_par_personne_par_semaine']
    try:
        horizon = int(ctx.get('horizon_semaines') or SCALE_SANITY['horizon_semaines'])
    except (TypeError, ValueError):
        horizon = SCALE_SANITY['horizon_semaines']

    cout_unitaire = SCALE_SANITY['cout_heures'].get(cle_cout, 4.0)
    requis = quantite * cout_unitaire
    disponible = taille * heures_semaine * horizon
    ratio = requis / disponible if disponible else float('inf')

    libelle_unite = _libelle_unite(cle_cout, quantite)
    personnes = f"{taille} personne{'s' if taille > 1 else ''}"
    detail = (
        f"{quantite} {libelle_unite} demandent environ {round(requis)} h de "
        f"travail. Une équipe de {personnes} qui consacre {round(heures_semaine)} h "
        f"par semaine au SEO dispose d'environ {round(disponible)} h sur "
        f"{horizon} semaines."
    )

    resultat = dict(base)
    resultat.update({
        'applicable': True,
        'quantite': quantite,
        'unite': libelle_unite,
        'unite_detectee': unite,
        'cle_cout': cle_cout,
        'cout_unitaire_heures': cout_unitaire,
        'heures_requises': round(requis, 1),
        'heures_disponibles': round(disponible, 1),
        'taille_equipe': taille,
        'horizon_semaines': horizon,
        'ratio': round(ratio, 2),
    })

    plafond = int(disponible * SCALE_SANITY['seuil_avertissement'] / cout_unitaire)
    plafond = max(1, plafond)

    if ratio > SCALE_SANITY['seuil_blocage']:
        resultat['niveau'] = 'blocage'
        resultat['quantite_realiste'] = plafond
        resultat['message'] = (
            f"{detail} Cette recommandation ne sera jamais exécutée telle quelle. "
            f"Visez {plafond} {_libelle_unite(cle_cout, plafond)} pour commencer, "
            "et rouvrez la question une fois que les premières auront donné un "
            "résultat."
        )
    elif ratio > SCALE_SANITY['seuil_avertissement']:
        resultat['niveau'] = 'avertissement'
        resultat['quantite_realiste'] = plafond
        resultat['message'] = (
            f"{detail} C'est {round(ratio * 100)} % de la capacité SEO de "
            "l'équipe : faisable seulement si rien d'autre ne passe avant."
        )
    else:
        resultat['niveau'] = 'ok'
        resultat['message'] = ''
    return resultat
