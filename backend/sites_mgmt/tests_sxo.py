"""Tests for the SXO page-type taxonomy and the SERP mismatch verdict.

Everything runs offline and without a database: `sxo` takes HTML and returns
data, so there is nothing to mock. Fixtures are written the way Quebec pages
actually ship (accents, "soumission", prices with the sign last) because that
is exactly what an English-only classifier would miss.

Run all:
    python manage.py test sites_mgmt.tests_sxo
"""
from django.test import SimpleTestCase

from .sxo import (
    LIBELLES_TYPES, TYPES_PAGE, classify_page_type, detect_mismatch,
    normalize_page_type,
)


def _page(titre='', tete='', corps=''):
    return (
        "<!doctype html><html lang='fr-CA'><head>"
        f"<meta charset='utf-8'><title>{titre}</title>{tete}"
        f"</head><body>{corps}</body></html>"
    )


def _remplissage(mots=800):
    phrase = "Le referencement local demande de la constance et du contenu utile. "
    texte = phrase * (mots // 11 + 1)
    return f"<p>{texte}</p>"


def _jsonld(charge):
    return f"<script type='application/ld+json'>{charge}</script>"


class ClassifyAccueilTests(SimpleTestCase):
    def test_racine_avec_schema_website(self):
        html = _page(
            titre='Gridar - le SEO qui roule tout seul',
            tete=_jsonld('{"@context":"https://schema.org","@type":"WebSite",'
                         '"name":"Gridar"}'),
            corps=(
                "<nav><a href='/tarifs'>Tarifs</a><a href='/blogue'>Blogue</a>"
                "<a href='/contact'>Contact</a></nav>"
                "<h1>Le SEO local qui roule tout seul</h1>"
                "<a class='btn' href='/inscription'>Essai gratuit</a>"
                "<p>Ils nous font confiance.</p>"
            ),
        )
        res = classify_page_type(html, 'https://gridar.app/')
        self.assertEqual(res['type'], 'accueil')
        self.assertEqual(res['libelle'], LIBELLES_TYPES['accueil'])
        self.assertGreater(res['confiance'], 0.3)


class ClassifyArticleTests(SimpleTestCase):
    def test_billet_de_blogue_quebecois(self):
        html = _page(
            titre='Tendances SEO 2026 pour les PME du Québec',
            tete=(
                _jsonld('{"@type":"BlogPosting","headline":"Tendances SEO 2026"}')
                + "<meta property='article:published_time' content='2026-05-12'>"
            ),
            corps=(
                "<h1>Tendances SEO 2026 pour les PME du Québec</h1>"
                "<p>Publié le 12 mai 2026 par Marie Tremblay</p>"
                + _remplissage(900)
                + "<h2>Articles similaires</h2><a href='/blogue/autre'>Autre texte</a>"
            ),
        )
        res = classify_page_type(html, 'https://exemple.ca/blogue/tendances-seo-2026')
        self.assertEqual(res['type'], 'article')
        self.assertGreater(res['scores']['article'], res['scores']['guide'])

    def test_signaux_expliquent_le_verdict(self):
        html = _page(
            titre='Tendances SEO 2026',
            tete=_jsonld('{"@type":"Article"}'),
            corps="<h1>Tendances</h1><p>Publié le 12 mai 2026</p>" + _remplissage(800),
        )
        res = classify_page_type(html, 'https://exemple.ca/blogue/tendances')
        self.assertTrue(res['signaux'])
        self.assertTrue(all(s['poids'] > 0 for s in res['signaux']))
        self.assertEqual(res['signaux'], sorted(res['signaux'], key=lambda s: -s['poids']))


class ClassifyGuideTests(SimpleTestCase):
    def test_guide_en_etapes_bat_article(self):
        html = _page(
            titre='Comment choisir un plombier fiable au Québec en 7 étapes',
            tete=_jsonld('{"@type":"BlogPosting"}'),
            corps=(
                "<h1>Comment choisir un plombier fiable en 7 étapes</h1>"
                "<p>Table des matières</p>"
                "<h2>Étape 1 : vérifier la licence RBQ</h2>"
                "<h2>Étape 2 : demander trois références</h2>"
                "<h2>Étape 3 : comparer les garanties</h2>"
                + _remplissage(1700)
            ),
        )
        res = classify_page_type(html, 'https://exemple.ca/blogue/comment-choisir-un-plombier')
        self.assertEqual(res['type'], 'guide')
        self.assertIn('article', res['alternatives'])


class ClassifyComparatifTests(SimpleTestCase):
    def test_page_vs_avec_tableau(self):
        lignes = ''.join(
            f"<tr><td>Critère {n}</td><td>Oui</td><td>Non</td></tr>" for n in range(5)
        )
        html = _page(
            titre='Gridar vs Semrush : le comparatif 2026',
            corps=(
                "<h1>Gridar vs Semrush</h1>"
                "<table><tr><th>Critère</th><th>Gridar</th><th>Semrush</th></tr>"
                f"{lignes}</table>"
                "<h2>Avantages et inconvénients</h2>" + _remplissage(600)
            ),
        )
        res = classify_page_type(html, 'https://gridar.app/comparatif/gridar-vs-semrush')
        self.assertEqual(res['type'], 'comparatif')
        self.assertGreater(res['confiance'], 0.5)


class ClassifyFicheProduitTests(SimpleTestCase):
    def test_fiche_avec_panier_et_prix(self):
        html = _page(
            titre='Tuque en laine mérinos - Boutique Nordique',
            tete=_jsonld('{"@type":"Product","name":"Tuque",'
                         '"offers":{"@type":"Offer","price":"39.99"}}'),
            corps=(
                "<h1>Tuque en laine mérinos</h1>"
                "<p>39,99 $</p><p>Disponibilité : en stock</p>"
                "<p>UGS : TUQ-001</p>"
                "<button>Ajouter au panier</button>"
            ),
        )
        res = classify_page_type(html, 'https://boutique.ca/produits/tuque-laine-merinos')
        self.assertEqual(res['type'], 'fiche_produit')

    def test_majuscules_et_accents_ne_cassent_rien(self):
        html = _page(
            titre='TUQUE EN LAINE MÉRINOS',
            corps=(
                "<h1>TUQUE EN LAINE MÉRINOS</h1><p>39,99 $</p>"
                "<p>DISPONIBILITÉ : EN STOCK</p>"
                "<button>AJOUTER AU PANIER</button>"
            ),
        )
        res = classify_page_type(html, 'https://boutique.ca/produits/tuque')
        self.assertEqual(res['type'], 'fiche_produit')


class ClassifyLandingServiceTests(SimpleTestCase):
    def test_page_de_service_avec_soumission(self):
        html = _page(
            titre='Déneigement résidentiel à Laval | Neige Plus',
            tete=_jsonld('{"@type":"Service","name":"Déneigement"}'),
            corps=(
                "<h1>Déneigement résidentiel</h1>"
                "<a class='btn' href='/soumission'>Demander une soumission</a>"
                "<h2>Notre processus</h2><h2>Témoignages</h2><h2>Nos forfaits</h2>"
                + _remplissage(400)
            ),
        )
        res = classify_page_type(html, 'https://neigeplus.ca/services/deneigement-residentiel')
        self.assertEqual(res['type'], 'landing_service')


class ClassifyPageLocaleTests(SimpleTestCase):
    def test_succursale_avec_nap_et_carte(self):
        html = _page(
            titre='Notre succursale de Laval | Neige Plus',
            tete=_jsonld('{"@type":"LocalBusiness","name":"Neige Plus Laval"}'),
            corps=(
                "<h1>Neige Plus Laval</h1>"
                "<address>1234 boul. des Laurentides, Laval, QC H7G 2W1</address>"
                "<p>Téléphone : (450) 555-1234</p>"
                "<h2>Heures d'ouverture</h2>"
                "<iframe src='https://www.google.com/maps/embed?pb=1'></iframe>"
                "<p>Secteurs desservis : Laval, Boisbriand, Rosemère.</p>"
            ),
        )
        res = classify_page_type(html, 'https://neigeplus.ca/succursales/laval')
        self.assertEqual(res['type'], 'page_locale')
        self.assertGreater(res['confiance'], 0.6)


class ClassifyOutilTests(SimpleTestCase):
    def test_calculateur_bat_le_contenu(self):
        html = _page(
            titre='Calculateur de taxes TPS et TVQ',
            corps=(
                "<h1>Calculateur de taxes TPS et TVQ</h1>"
                "<p>Entrez votre montant avant taxes.</p>"
                "<form><input type='number' name='montant'>"
                "<input type='number' name='taux'>"
                "<button>Calculer</button></form>"
                "<div id='resultat'></div>" + _remplissage(500)
            ),
        )
        res = classify_page_type(html, 'https://gridar.app/outils/calculateur-de-taxes')
        self.assertEqual(res['type'], 'outil')


class ClassifyCategorieTests(SimpleTestCase):
    def test_index_de_blogue(self):
        cartes = ''.join(
            f"<article><a href='/blogue/texte-{n}'>Texte {n}</a></article>"
            for n in range(10)
        )
        html = _page(
            titre='Nos articles | Exemple',
            corps=(
                "<h1>Nos articles</h1>" + cartes
                + "<div class='pagination'><a href='/blogue/page/2'>Page 2 sur 5</a></div>"
            ),
        )
        res = classify_page_type(html, 'https://exemple.ca/blogue/')
        self.assertEqual(res['type'], 'categorie')


class ClassifyRobustesseTests(SimpleTestCase):
    def test_html_vide_retombe_sur_article(self):
        res = classify_page_type('', '')
        self.assertEqual(res['type'], 'article')
        self.assertEqual(res['confiance'], 0.15)
        self.assertTrue(res['notes'])

    def test_html_casse_ne_leve_pas(self):
        res = classify_page_type('<html><body><div><p>Bonjour <b>monde', 'https://x.ca/a')
        self.assertIn(res['type'], TYPES_PAGE)

    def test_entrees_none_tolerees(self):
        res = classify_page_type(None, None)
        self.assertIn(res['type'], TYPES_PAGE)

    def test_scores_couvrent_toute_la_taxonomie(self):
        res = classify_page_type(_page(titre='Test'), 'https://x.ca/a')
        self.assertEqual(set(res['scores']), set(TYPES_PAGE))
        self.assertTrue(0.15 <= res['confiance'] <= 0.95)

    def test_page_hybride_signalee(self):
        html = _page(
            titre='Le déneigement commercial expliqué',
            tete=(_jsonld('{"@type":"BlogPosting"}')
                  + _jsonld('{"@type":"Service","name":"Déneigement commercial"}')),
            corps=(
                "<h1>Le déneigement commercial expliqué</h1>"
                "<p>Publié le 3 novembre 2026 par Éric Roy</p>"
                "<a class='btn' href='/soumission'>Demander une soumission</a>"
                "<h2>Notre processus</h2><h2>Témoignages</h2><h2>Nos forfaits</h2>"
                + _remplissage(900)
            ),
        )
        res = classify_page_type(html, 'https://neigeplus.ca/blogue/deneigement-commercial')
        self.assertTrue(res['hybride'])
        self.assertTrue(any('hybride' in note.lower() for note in res['notes']))


class ClassifyCasLimitesTests(SimpleTestCase):
    """Cases where a naive classifier gets it wrong."""

    def test_page_anglaise_reste_classee(self):
        html = _page(
            titre='How to choose a plumber in 7 steps',
            tete=_jsonld('{"@type":"Article"}'),
            corps=(
                "<h1>How to choose a plumber in 7 steps</h1>"
                "<h2>Step 1: check the licence</h2><h2>Step 2: ask around</h2>"
                "<h2>Step 3: compare quotes</h2>" + _remplissage(1600)
            ),
        )
        res = classify_page_type(html, 'https://example.com/blog/how-to-choose-a-plumber')
        self.assertEqual(res['type'], 'guide')

    def test_fiche_produit_sans_schema_ni_url_parlante(self):
        html = _page(
            titre='Pelle à neige ergonomique 24 pouces',
            corps=(
                "<h1>Pelle à neige ergonomique</h1><p>54,95 $</p>"
                "<p>En stock - livraison gratuite</p>"
                "<div class='product-add-to-cart'><button>Ajouter au panier</button></div>"
            ),
        )
        res = classify_page_type(html, 'https://quincaillerie.ca/p/pelle-neige-24')
        self.assertEqual(res['type'], 'fiche_produit')

    def test_outil_sans_segment_outils(self):
        html = _page(
            titre='Simulateur de paiements hypothécaires',
            corps=(
                "<h1>Simulateur de paiements hypothécaires</h1>"
                "<p>Entrez votre montant et votre taux.</p>"
                "<form><input type='number'><input type='range'>"
                "<select><option>25 ans</option></select>"
                "<button>Calculer</button></form><div class='resultat'></div>"
            ),
        )
        res = classify_page_type(html, 'https://banque.ca/simulateur-hypotheque')
        self.assertEqual(res['type'], 'outil')

    def test_accueil_de_commerce_local_devient_page_locale(self):
        html = _page(
            titre='Plomberie Gagnon | Plombier à Montréal 24/7',
            tete=_jsonld('{"@type":"Plumber","name":"Plomberie Gagnon"}'),
            corps=(
                "<h1>Plombier à Montréal</h1>"
                "<address>4500 rue Sherbrooke Est, Montréal, QC H1X 2A1</address>"
                "<p>(514) 555-9090</p><h2>Heures d'ouverture</h2>"
                "<iframe src='https://www.google.com/maps/embed?pb=2'></iframe>"
                + _remplissage(300)
            ),
        )
        res = classify_page_type(html, 'https://plomberiegagnon.ca/')
        self.assertEqual(res['type'], 'page_locale')
        self.assertIn('accueil', res['alternatives'])

    def test_categorie_de_boutique_pas_fiche_produit(self):
        cartes = ''.join(
            f"<article><a href='/produits/tuque-{n}'>Tuque {n}</a><span>39,99 $</span></article>"
            for n in range(12)
        )
        html = _page(
            titre='Tuques et bonnets | Boutique Nordique',
            corps="<h1>Tuques et bonnets</h1><p>Trier par : popularité</p>" + cartes,
        )
        res = classify_page_type(html, 'https://boutique.ca/produits/')
        self.assertEqual(res['type'], 'categorie')

    def test_page_vide_de_texte_signale_le_rendu_js(self):
        html = _page(
            titre='Déneigement commercial',
            tete=_jsonld('{"@type":"Service"}'),
            corps="<div id='root'></div>",
        )
        res = classify_page_type(html, 'https://neigeplus.ca/services/commercial')
        self.assertTrue(any('JavaScript' in note for note in res['notes']))

    def test_listing_ne_declenche_pas_l_alerte_de_rendu(self):
        cartes = ''.join(
            f"<article><a href='/blogue/texte-{n}'>Texte {n}</a></article>" for n in range(10)
        )
        res = classify_page_type(_page(titre='Archives', corps=cartes),
                                 'https://exemple.ca/blogue/')
        self.assertFalse(any('JavaScript' in note for note in res['notes']))


class NormalizeTypeTests(SimpleTestCase):
    def test_libelles_amont_anglais(self):
        attendu = {
            'Blog Post': 'article',
            'Product Page': 'fiche_produit',
            'Comparison Page': 'comparatif',
            'Landing Page': 'landing_service',
            'Service Page': 'landing_service',
            'Local Page': 'page_locale',
            'Tool / Interactive': 'outil',
            'Hybrid (Service + Content)': 'landing_service',
            'Homepage': 'accueil',
            'Category page': 'categorie',
        }
        for brut, cle in attendu.items():
            self.assertEqual(normalize_page_type(brut), cle, brut)

    def test_libelles_francais(self):
        for brut, cle in (
            ('fiche produit', 'fiche_produit'),
            ('Page locale', 'page_locale'),
            ('articles de blogue', 'article'),
            ('Calculateur', 'outil'),
            ('guide pratique', 'guide'),
        ):
            self.assertEqual(normalize_page_type(brut), cle, brut)

    def test_inconnu_rend_vide(self):
        for brut in ('', None, 'zzz', '???'):
            self.assertEqual(normalize_page_type(brut), '')


class DetectMismatchTests(SimpleTestCase):
    def test_type_aligne(self):
        res = detect_mismatch('article', ['article'] * 6 + ['guide'] * 4)
        self.assertEqual(res['verdict'], 'aligne')
        self.assertEqual(res['severite'], 'aucune')
        self.assertEqual(res['type_dominant'], 'article')

    def test_article_contre_fiches_produit_est_critique(self):
        res = detect_mismatch('article', ['fiche_produit'] * 7 + ['comparatif'] * 3)
        self.assertEqual(res['verdict'], 'desalignement')
        self.assertEqual(res['severite'], 'critique')
        self.assertEqual(res['type_dominant'], 'fiche_produit')
        self.assertEqual(res['force_consensus'], 'fort')
        self.assertIn('fiche produit', res['recommandation'].lower())

    def test_article_contre_comparatifs_est_eleve(self):
        res = detect_mismatch('article', ['comparatif'] * 6 + ['fiche_produit'] * 4)
        self.assertEqual(res['severite'], 'elevee')

    def test_consensus_mixte_abaisse_la_severite(self):
        serp = ['comparatif'] * 5 + ['fiche_produit'] * 3 + ['outil'] * 2
        res = detect_mismatch('article', serp)
        self.assertEqual(res['force_consensus'], 'mixte')
        self.assertEqual(res['severite'], 'moyenne')
        self.assertTrue(any('mixte' in note for note in res['notes']))

    def test_mon_type_present_abaisse_la_severite(self):
        res = detect_mismatch('article', ['fiche_produit'] * 6 + ['article'] * 4)
        self.assertEqual(res['severite'], 'elevee')
        self.assertEqual(res['part_de_mon_type'], 0.4)

    def test_serp_fragmentee(self):
        serp = ['fiche_produit'] * 3 + ['comparatif'] * 3 + ['outil'] * 2 + ['guide'] * 2
        res = detect_mismatch('article', serp)
        self.assertEqual(res['verdict'], 'serp_fragmente')
        self.assertEqual(res['force_consensus'], 'fragmente')
        self.assertIn('fragment', res['recommandation'].lower())

    def test_meme_famille_reste_leger(self):
        res = detect_mismatch('guide', ['article'] * 8 + ['comparatif'] * 2)
        self.assertEqual(res['verdict'], 'desalignement_leger')
        self.assertEqual(res['severite'], 'faible')

    def test_libelles_anglais_acceptes(self):
        res = detect_mismatch('Blog Post', ['Product Page'] * 7 + ['Comparison'] * 3)
        self.assertEqual(res['type_page'], 'article')
        self.assertEqual(res['type_dominant'], 'fiche_produit')
        self.assertEqual(res['severite'], 'critique')

    def test_petit_echantillon_marque_la_fiabilite(self):
        res = detect_mismatch('article', ['outil'] * 3)
        self.assertEqual(res['fiabilite'], 'faible')
        self.assertEqual(res['echantillon'], 3)
        self.assertTrue(any('chantillon' in note for note in res['notes']))

    def test_serp_vide_indetermine(self):
        res = detect_mismatch('article', [])
        self.assertEqual(res['verdict'], 'indetermine')
        self.assertTrue(res['recommandation'])

    def test_types_serp_illisibles(self):
        res = detect_mismatch('article', ['zzz', 'yyy'])
        self.assertEqual(res['verdict'], 'indetermine')
        self.assertEqual(res['repartition'], {'inconnu': 2})

    def test_type_de_page_inconnu(self):
        res = detect_mismatch('licorne', ['article'] * 10)
        self.assertEqual(res['verdict'], 'indetermine')
        self.assertEqual(res['libelle_page'], 'Inconnu')

    def test_resultats_non_classes_notes_mais_exclus(self):
        res = detect_mismatch('article', ['outil'] * 6 + ['zzz'] * 4)
        self.assertEqual(res['type_dominant'], 'outil')
        self.assertEqual(res['repartition']['inconnu'], 4)
        self.assertTrue(any('non classés' in note for note in res['notes']))

    def test_chaine_bout_en_bout(self):
        html = _page(
            titre='Comment déneiger une entrée en 5 étapes',
            tete=_jsonld('{"@type":"BlogPosting"}'),
            corps=(
                "<h1>Comment déneiger une entrée en 5 étapes</h1>"
                "<h2>Étape 1 : dégager le seuil</h2>"
                "<h2>Étape 2 : choisir la pelle</h2>"
                "<h2>Étape 3 : finir les bordures</h2>" + _remplissage(1600)
            ),
        )
        page = classify_page_type(html, 'https://neigeplus.ca/blogue/comment-deneiger')
        res = detect_mismatch(page['type'], ['Local Page'] * 7 + ['Service Page'] * 3)
        self.assertEqual(page['type'], 'guide')
        self.assertEqual(res['type_dominant'], 'page_locale')
        self.assertEqual(res['severite'], 'critique')
