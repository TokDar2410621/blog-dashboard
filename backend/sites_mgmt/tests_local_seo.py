"""Tests for the local SEO grid, NAP reading and vertical detection.

Everything runs offline: the four public functions take data and return data,
so there is nothing to mock. The address and phone fixtures are the shapes a
Saguenay footer really uses, because that is where every previous reader broke.

Run all:
    python manage.py test sites_mgmt.tests_local_seo
"""
from datetime import date, timedelta

from django.test import SimpleTestCase

from .html_parse import extract_seo_signals
from .local_seo import (
    DIMENSIONS, SEVERITES, VERTICALES, compare_nap, detect_vertical,
    extract_nap, score_local_seo,
)


def page(corps: str = '', tete: str = '', pied: str = '',
         titre: str = 'Services de plomberie | Plomberie Rive-Nord') -> str:
    """One document, with only the region under test filled in."""
    return f"""<!doctype html>
<html lang="fr-CA"><head><meta charset="utf-8">
<title>{titre}</title>
{tete}
</head>
<body>
<main><h1>Plombier à Chicoutimi</h1><p>{corps or 'Texte de la page.'}</p></main>
<footer>{pied}</footer>
</body></html>"""


def adresse_de(ligne: str):
    """The address `extract_nap` retains from an <address> block."""
    return extract_nap(page(pied=f'<address>{ligne}</address>'))['adresse']


def telephone_de(ligne: str):
    return extract_nap(page(pied=f'<p>{ligne}</p>'))['telephone']


JSONLD_LOCAL = """<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Plumber",
 "name":"Plomberie Rive-Nord",
 "telephone":"(418) 555-1234",
 "address":{"@type":"PostalAddress","streetAddress":"1234, boul. Talbot",
            "addressLocality":"Chicoutimi","addressRegion":"QC",
            "postalCode":"G7H 2B1"},
 "openingHours":"Mo-Fr 08:00-17:00",
 "sameAs":["https://g.page/plomberie-rive-nord"]}
</script>"""

MICRODATA_LOCAL = """
<div itemscope itemtype="https://schema.org/Plumber">
  <span itemprop="name">Plomberie Rive-Nord</span>
  <div itemprop="address" itemscope itemtype="https://schema.org/PostalAddress">
    <span itemprop="streetAddress">1234, boul. Talbot</span>
    <span itemprop="addressLocality">Chicoutimi</span>
    <span itemprop="addressRegion">QC</span>
    <span itemprop="postalCode">G7H 2B1</span>
  </div>
  <span itemprop="telephone">418 555-1234</span>
</div>"""


class ConstantesTests(SimpleTestCase):
    def test_les_poids_font_cent(self):
        self.assertEqual(sum(poids for _, _, poids in DIMENSIONS), 100)
        self.assertEqual(
            [poids for _, _, poids in DIMENSIONS], [25, 20, 20, 15, 10, 10],
        )

    def test_les_six_verticales_sont_declarees(self):
        cles = [entree[0] for entree in VERTICALES]
        self.assertEqual(sorted(cles), sorted([
            'restauration', 'sante', 'construction', 'services_professionnels',
            'commerce_detail', 'automobile',
        ]))
        for cle, libelle, schema, forts, faibles in VERTICALES:
            self.assertTrue(libelle and schema, cle)
            self.assertTrue(forts and faibles, cle)

    def test_severites_ordonnees_du_moindre_au_pire(self):
        self.assertEqual(SEVERITES[0], 'aucune')
        self.assertEqual(SEVERITES[-1], 'critique')


class TelephoneTests(SimpleTestCase):
    def test_les_formats_quebecois(self):
        for ecrit in ('(418) 555-1234', '418-555-1234', '418 555 1234',
                      '418.555.1234', '1 418 555-1234', '+1 (418) 555-1234',
                      '4185551234'):
            trouve = telephone_de(f'Téléphone : {ecrit}')
            self.assertIsNotNone(trouve, ecrit)
            self.assertEqual(trouve['chiffres'], '4185551234', ecrit)

    def test_affichage_normalise(self):
        self.assertEqual(telephone_de('Tél. 418.555.1234')['valeur'],
                         '(418) 555-1234')

    def test_le_poste_est_conserve(self):
        trouve = telephone_de('418 555-1234 poste 221')
        self.assertEqual(trouve['poste'], '221')
        self.assertIn('poste 221', trouve['valeur'])

    def test_un_indicatif_impossible_est_refuse(self):
        self.assertIsNone(telephone_de('Numéro de dossier 018 555-1234'))

    def test_ni_une_annee_ni_un_prix_ne_sont_un_numero(self):
        self.assertIsNone(telephone_de(
            'Depuis 1995, plus de 1 000 clients et 12 500,50 $ économisés.'))

    def test_le_lien_tel_prime_sur_le_texte(self):
        html = page(pied='<a href="tel:+14185551234">Appelez-nous</a>'
                         '<p>Fournisseur : 514 555-9999</p>')
        nap = extract_nap(html)
        self.assertEqual(nap['telephone']['chiffres'], '4185551234')
        self.assertEqual(nap['telephone']['source'], 'lien_tel')
        self.assertTrue(nap['tel_cliquable'])
        self.assertIn('5145559999',
                      [item['chiffres'] for item in nap['candidats']['telephone']])


class AdresseTests(SimpleTestCase):
    def test_adresse_quebecoise_complete(self):
        trouve = adresse_de('1234, boul. Talbot, app. 5, Chicoutimi (Québec) G7H 2B1')
        composants = trouve['composants']
        self.assertEqual(composants['numero'], '1234')
        self.assertEqual(composants['voie'], 'boul. Talbot')
        self.assertEqual(composants['unite'], '5')
        self.assertEqual(composants['ville'], 'Chicoutimi')
        self.assertEqual(composants['province'], 'QC')
        self.assertEqual(composants['code_postal'], 'G7H 2B1')

    def test_les_accents_de_la_page_sont_conserves(self):
        trouve = adresse_de('455, rue Racine Est, Chicoutimi (Québec) G7H 1T5')
        self.assertIn('Québec', trouve['valeur'])

    def test_voie_ordinale(self):
        composants = adresse_de('12, 3e Avenue, Limoilou, QC G1L 2W3')['composants']
        self.assertEqual(composants['numero'], '12')
        self.assertEqual(composants['voie'], '3e Avenue')
        self.assertEqual(composants['ville'], 'Limoilou')

    def test_voie_abregee_sans_virgule_avant_la_ville(self):
        composants = adresse_de('1000 ch. du Lac Alma QC G8B 5W1')['composants']
        self.assertEqual(composants['voie'], 'ch. du Lac')
        self.assertEqual(composants['ville'], 'Alma')
        self.assertEqual(composants['province'], 'QC')

    def test_la_ville_ne_devient_pas_la_province(self):
        composants = adresse_de(
            '5000, boulevard Wilfrid-Hamel, Québec (Québec) G1P 2J7')['composants']
        self.assertEqual(composants['ville'], 'Québec')
        self.assertEqual(composants['province'], 'QC')

    def test_code_postal_sans_espace(self):
        composants = adresse_de('300, rue Saint-Dominique, Jonquière, QC G7X4B4')['composants']
        self.assertEqual(composants['code_postal'], 'G7X 4B4')

    def test_la_ligne_est_coupee_avant_le_telephone(self):
        trouve = adresse_de('1234, boul. Talbot, Chicoutimi | Tél. : 418 555-1234')
        self.assertNotIn('418', trouve['valeur'])

    def test_une_phrase_ordinaire_nest_pas_une_adresse(self):
        self.assertIsNone(adresse_de(
            "Nous sommes ouverts depuis 1995 et desservons toute la région."))


class ExtractNapTests(SimpleTestCase):
    def test_pied_de_page_complet(self):
        html = page(pied=(
            '<address>1234, boul. Talbot, Chicoutimi (Québec) G7H 2B1</address>'
            '<p><a href="tel:+14185551234">418 555-1234</a></p>'
            '<p>&copy; 2026 Plomberie Rive-Nord inc. Tous droits réservés.</p>'
        ))
        nap = extract_nap(html)
        self.assertTrue(nap['complet'])
        self.assertEqual(nap['champs_manquants'], [])
        self.assertEqual(nap['nom']['valeur'], 'Plomberie Rive-Nord inc')
        self.assertEqual(nap['adresse']['source'], 'balise_address')
        self.assertEqual(nap['telephone']['source'], 'lien_tel')

    def test_le_jsonld_prime_sur_le_pied_de_page(self):
        html = page(
            tete=JSONLD_LOCAL,
            pied='<address>9999, rue Autre, Alma (Québec) G8B 1A1</address>'
                 '<p>418 555-9999</p>',
        )
        nap = extract_nap(html)
        for champ in ('nom', 'telephone', 'adresse'):
            self.assertEqual(nap[champ]['source'], 'jsonld', champ)
        self.assertEqual(nap['adresse']['composants']['ville'], 'Chicoutimi')
        self.assertGreaterEqual(len(nap['candidats']['adresse']), 2)

    def test_microdonnees_lues(self):
        nap = extract_nap(page(pied=MICRODATA_LOCAL))
        self.assertEqual(nap['nom']['source'], 'microdata')
        self.assertEqual(nap['telephone']['chiffres'], '4185551234')
        self.assertEqual(nap['adresse']['composants']['code_postal'], 'G7H 2B1')

    def test_nom_tire_du_titre(self):
        nap = extract_nap(page(titre='Débouchage de drain à Chicoutimi | Plomberie Rive-Nord'))
        self.assertEqual(nap['nom']['valeur'], 'Plomberie Rive-Nord')
        self.assertEqual(nap['nom']['source'], 'titre')

    def test_nom_tire_de_og_site_name(self):
        nap = extract_nap(page(
            titre='Accueil',
            tete='<meta property="og:site_name" content="Plomberie Rive-Nord">'))
        self.assertEqual(nap['nom']['source'], 'meta_og')

    def test_une_mention_legale_nest_pas_un_nom(self):
        nap = extract_nap(page(titre='Accueil',
                               pied='<p>&copy; 2026 Tous droits réservés.</p>'))
        self.assertIsNone(nap['nom'])

    def test_page_sans_nap(self):
        nap = extract_nap(page(titre='Accueil'))
        self.assertFalse(nap['complet'])
        self.assertEqual(sorted(nap['champs_manquants']),
                         ['adresse', 'nom', 'telephone'])
        self.assertFalse(nap['tel_cliquable'])

    def test_carte_et_fiche_google(self):
        nap = extract_nap(page(pied=(
            '<a href="https://maps.app.goo.gl/abcd">Notre fiche</a>'
            '<iframe src="https://www.google.com/maps/embed?pb=x"></iframe>'
            '<form action="/contact"><input name="q"></form>'
        )))
        self.assertTrue(nap['fiche_google'])
        self.assertTrue(nap['carte'])
        self.assertTrue(nap['formulaire'])

    def test_markup_casse_ne_leve_rien(self):
        casse = ('<html><body><footer><address>1234, boul. Talbot, Chicoutimi '
                 '(Québec) G7H 2B1<p>418 555-1234</footer></div></html>')
        nap = extract_nap(casse)
        self.assertEqual(nap['telephone']['chiffres'], '4185551234')
        self.assertIsNotNone(nap['adresse'])

    def test_entrees_vides(self):
        for valeur in ('', None, '   '):
            nap = extract_nap(valeur)
            self.assertFalse(nap['complet'])


class CompareNapNormalisationTests(SimpleTestCase):
    """Everything here must come back coherent: same NAP, different writing."""

    def comparer(self, **remplacements):
        site = {
            'source': 'Site web',
            'nom': 'Plomberie Rive-Nord inc.',
            'adresse': '1234, boul. Talbot, Chicoutimi (Québec) G7H 2B1',
            'telephone': '(418) 555-1234',
        }
        fiche = dict(site, source='Fiche Google')
        fiche.update(remplacements)
        return compare_nap([site, fiche])

    def test_abreviation_de_voie(self):
        resultat = self.comparer(
            adresse='1234 boulevard Talbot, Chicoutimi, QC G7H 2B1')
        self.assertTrue(resultat['coherent'], resultat['divergences'])
        self.assertEqual(resultat['severite'], 'aucune')

    def test_formats_de_telephone(self):
        for ecrit in ('418-555-1234', '1 418 555 1234', '4185551234',
                      '+1 (418) 555-1234'):
            resultat = self.comparer(telephone=ecrit)
            self.assertTrue(resultat['coherent'], ecrit)

    def test_forme_juridique_et_casse(self):
        resultat = self.comparer(nom='PLOMBERIE RIVE-NORD')
        self.assertTrue(resultat['coherent'], resultat['divergences'])

    def test_accents_et_province_ecrite_au_long(self):
        resultat = self.comparer(
            adresse='1234, Boul Talbot, CHICOUTIMI, Quebec, G7H 2B1')
        self.assertTrue(resultat['coherent'], resultat['divergences'])

    def test_ordinal_ecrit_autrement(self):
        resultat = compare_nap([
            {'source': 'Site', 'adresse': '12, 3e Avenue, Limoilou, QC G1L 2W3'},
            {'source': 'Google', 'adresse': '12 3ième avenue, Limoilou, QC G1L 2W3'},
        ])
        self.assertTrue(resultat['coherent'], resultat['divergences'])

    def test_abreviation_de_local(self):
        resultat = self.comparer(
            adresse='1234, boul. Talbot, bureau 5, Chicoutimi (Québec) G7H 2B1')
        # "app. 5" against "bureau 5" is the same door; the site simply has no
        # unit at all here, which is reported as an absence, not a divergence.
        self.assertTrue(resultat['champs']['adresse']['coherent'])


class CompareNapDivergenceTests(SimpleTestCase):
    def comparer(self, gauche, droite, champ='adresse'):
        return compare_nap([
            {'source': 'Site', champ: gauche},
            {'source': 'Fiche Google', champ: droite},
        ])

    def divergence(self, resultat, champ, composant=None):
        for item in resultat['divergences']:
            if item['champ'] == champ and item['composant'] == composant:
                return item
        raise AssertionError(
            f'divergence {champ}/{composant} absente de '
            f"{[(d['champ'], d['composant']) for d in resultat['divergences']]}")

    def test_numero_civique_est_critique(self):
        resultat = self.comparer(
            '1234, boul. Talbot, Chicoutimi, QC G7H 2B1',
            '1240, boul. Talbot, Chicoutimi, QC G7H 2B1')
        self.assertFalse(resultat['coherent'])
        self.assertEqual(self.divergence(resultat, 'adresse', 'numero')['severite'],
                         'critique')
        self.assertEqual(resultat['severite'], 'critique')

    def test_ville_est_elevee(self):
        resultat = self.comparer(
            '1234, boul. Talbot, Chicoutimi, QC G7H 2B1',
            '1234, boul. Talbot, Jonquière, QC G7H 2B1')
        self.assertEqual(self.divergence(resultat, 'adresse', 'ville')['severite'],
                         'elevee')

    def test_code_postal_est_moyen(self):
        resultat = self.comparer(
            '1234, boul. Talbot, Chicoutimi, QC G7H 2B1',
            '1234, boul. Talbot, Chicoutimi, QC G7H 9Z9')
        self.assertEqual(
            self.divergence(resultat, 'adresse', 'code_postal')['severite'], 'moyenne')

    def test_numero_de_local_est_faible(self):
        resultat = self.comparer(
            '1234, boul. Talbot, app. 5, Chicoutimi, QC G7H 2B1',
            '1234, boul. Talbot, app. 7, Chicoutimi, QC G7H 2B1')
        self.assertEqual(self.divergence(resultat, 'adresse', 'unite')['severite'],
                         'faible')
        self.assertEqual(resultat['severite'], 'faible')

    def test_numero_de_telephone_different_est_critique(self):
        resultat = self.comparer('418 555-1234', '418 555-9999', champ='telephone')
        self.assertFalse(resultat['coherent'])
        self.assertEqual(self.divergence(resultat, 'telephone')['severite'], 'critique')

    def test_meme_numero_poste_different_est_faible(self):
        resultat = self.comparer('418 555-1234', '418 555-1234 poste 2',
                                 champ='telephone')
        self.assertEqual(self.divergence(resultat, 'telephone', 'poste')['severite'],
                         'faible')

    def test_nom_inclus_dans_lautre_est_faible(self):
        resultat = self.comparer('Plomberie Rive-Nord',
                                 'Plomberie Rive-Nord Saguenay', champ='nom')
        self.assertEqual(self.divergence(resultat, 'nom')['severite'], 'faible')

    def test_nom_franchement_different_est_moyen(self):
        resultat = self.comparer('Plomberie Rive-Nord', 'Drainage Expert',
                                 champ='nom')
        self.assertEqual(self.divergence(resultat, 'nom')['severite'], 'moyenne')

    def test_les_divergences_sortent_de_la_pire_a_la_moindre(self):
        resultat = compare_nap([
            {'source': 'Site', 'nom': 'Plomberie Rive-Nord',
             'adresse': '1234, boul. Talbot, app. 5, Chicoutimi, QC G7H 2B1',
             'telephone': '418 555-1234'},
            {'source': 'Google', 'nom': 'Plomberie Rive-Nord',
             'adresse': '1234, boul. Talbot, app. 7, Chicoutimi, QC G7H 9Z9',
             'telephone': '418 555-9999'},
        ])
        severites = [item['severite'] for item in resultat['divergences']]
        rangs = [SEVERITES.index(nom) for nom in severites]
        self.assertEqual(rangs, sorted(rangs, reverse=True))
        self.assertEqual(severites[0], 'critique')

    def test_champ_absent_dune_source(self):
        resultat = compare_nap([
            {'source': 'Site', 'nom': 'Plomberie Rive-Nord',
             'telephone': '418 555-1234'},
            {'source': 'Google', 'nom': 'Plomberie Rive-Nord'},
        ])
        manque = self.divergence(resultat, 'telephone', 'absent')
        self.assertEqual(manque['severite'], 'faible')
        self.assertIn('Google', resultat['champs']['telephone']['absent'])
        # An incomplete listing is not a contradiction: nothing diverges.
        self.assertTrue(resultat['coherent'])

    def test_une_seule_source(self):
        resultat = compare_nap([{'source': 'Site', 'nom': 'Plomberie Rive-Nord'}])
        self.assertTrue(resultat['coherent'])
        self.assertEqual(resultat['severite'], 'aucune')
        self.assertIn('deux sources', resultat['resume'])

    def test_aucune_source(self):
        resultat = compare_nap([])
        self.assertTrue(resultat['coherent'])
        self.assertEqual(resultat['sources'], [])

    def test_sortie_dextract_nap_utilisable_telle_quelle(self):
        nap = extract_nap(page(tete=JSONLD_LOCAL))
        nap['source'] = 'Site web'
        resultat = compare_nap([nap, {
            'source': 'Fiche Google',
            'nom': 'Plomberie Rive-Nord inc.',
            'adresse': '1234 boulevard Talbot, Chicoutimi, QC G7H 2B1',
            'telephone': '418-555-1234',
        }])
        self.assertTrue(resultat['coherent'], resultat['divergences'])

    def test_composants_fournis_en_dictionnaire(self):
        resultat = compare_nap([
            {'source': 'Site', 'adresse': {
                'rue': '1234, boul. Talbot', 'ville': 'Chicoutimi',
                'province': 'QC', 'code_postal': 'G7H 2B1'}},
            {'source': 'Google',
             'adresse': '1234 boulevard Talbot, Chicoutimi, QC G7H 2B1'},
        ])
        self.assertTrue(resultat['coherent'], resultat['divergences'])


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

CORPS_LOCAL = (
    "Notre équipe de plombiers dessert Chicoutimi, Jonquière et La Baie depuis "
    "1995. Un camion part de Chicoutimi en moins de trente minutes vers tout le "
    "Saguenay, et nous connaissons les vieux drains de Jonquière mieux que "
    "personne."
)

LIENS_LOCAUX = (
    '<a href="/plombier-jonquiere/">Plombier à Jonquière</a>'
    '<a href="/plombier-la-baie/">Plombier à La Baie</a>'
    '<a href="/plombier-alma/">Plombier à Alma</a>'
    '<a href="https://www.ccisaguenay.qc.ca/">Chambre de commerce</a>'
    '<a href="https://ville.saguenay.qc.ca/">Ville de Saguenay</a>'
    '<a href="https://maps.app.goo.gl/abcd">Notre fiche Google</a>'
)

PIED_LOCAL = (
    '<address>1234, boul. Talbot, Chicoutimi (Québec) G7H 2B1</address>'
    '<p><a href="tel:+14185551234">418 555-1234</a></p>'
    '<form action="/contact"><input name="courriel"></form>'
)


def page_locale() -> str:
    return page(
        corps=CORPS_LOCAL + LIENS_LOCAUX,
        tete=(JSONLD_LOCAL
              + '<meta name="description" content="Plombier à Chicoutimi et Jonquière.">'),
        pied=PIED_LOCAL,
        titre='Plombier à Chicoutimi | Plomberie Rive-Nord',
    )


def gbp_complete() -> dict:
    return {
        'revendiquee': True,
        'categorie': 'Plombier',
        'description': 'Plomberie résidentielle à Chicoutimi. ' * 6,
        'horaires': {'lundi': '08:00-17:00'},
        'photos': 24,
        'derniere_publication': date.today() - timedelta(days=6),
        'site_web': 'https://plomberie-rive-nord.ca',
    }


def avis_complets() -> dict:
    return {
        'total': 68,
        'moyenne': 4.7,
        'taux_reponse': 0.95,
        'dernier': date.today() - timedelta(days=12),
    }


def note(**arguments) -> dict:
    html = arguments.pop('html', page_locale())
    signals = extract_seo_signals(html, 'https://plomberie-rive-nord.ca/chicoutimi/')
    arguments.setdefault('nap', extract_nap(html))
    return score_local_seo(signals, **arguments)


class ScoreLocalTests(SimpleTestCase):
    def test_page_complete_avec_toutes_les_donnees(self):
        resultat = note(gbp=gbp_complete(), reviews=avis_complets())
        self.assertEqual(resultat['couverture'], 100.0)
        self.assertEqual(resultat['dimensions_non_mesurees'], [])
        self.assertGreaterEqual(resultat['score'], 90)
        for cle, detail in resultat['dimensions'].items():
            self.assertTrue(detail['applicable'], cle)
            self.assertEqual(detail['statut'], 'reussi', cle)

    def test_les_dimensions_gardent_leurs_poids(self):
        resultat = note(gbp=gbp_complete(), reviews=avis_complets())
        poids = {cle: detail['poids'] for cle, detail in resultat['dimensions'].items()}
        self.assertEqual(poids, {cle: valeur for cle, _, valeur in DIMENSIONS})
        self.assertEqual(sum(poids.values()), 100)

    def test_dimension_sans_donnee_sort_du_denominateur(self):
        resultat = note(gbp=gbp_complete())
        self.assertIn('avis', resultat['dimensions_non_mesurees'])
        avis = resultat['dimensions']['avis']
        self.assertFalse(avis['applicable'])
        self.assertIsNone(avis['note'])
        self.assertEqual(avis['max'], 0.0)
        self.assertEqual(resultat['couverture'], 80.0)
        self.assertTrue(avis['non_mesure'])

    def test_absence_de_donnee_ne_vaut_pas_un_zero(self):
        sans = note(gbp=gbp_complete())
        mauvais = note(gbp=gbp_complete(), reviews={
            'total': 1, 'moyenne': 2.1, 'taux_reponse': 0.0,
            'dernier': date.today() - timedelta(days=900),
        })
        bons = note(gbp=gbp_complete(), reviews=avis_complets())
        self.assertEqual(sans['score'], bons['score'])
        self.assertLess(mauvais['score'], sans['score'])

    def test_deux_dimensions_hors_denominateur(self):
        resultat = note()
        self.assertEqual(sorted(resultat['dimensions_non_mesurees']),
                         ['avis', 'fiche_google'])
        self.assertEqual(resultat['couverture'], 100.0 - 25 - 20)

    def test_une_cle_absente_de_la_fiche_sort_du_denominateur(self):
        partielle = {'revendiquee': True, 'categorie': 'Plombier'}
        resultat = note(gbp=partielle, reviews=avis_complets())
        fiche = resultat['dimensions']['fiche_google']
        self.assertTrue(fiche['applicable'])
        self.assertEqual(fiche['note'], 100)
        self.assertEqual(fiche['verifications']['faites'], 2)
        self.assertGreaterEqual(fiche['verifications']['ignorees'], 4)

    def test_fiche_non_revendiquee_est_critique(self):
        gbp = gbp_complete()
        gbp['revendiquee'] = False
        resultat = note(gbp=gbp, reviews=avis_complets())
        codes = {reco['code']: reco for reco in resultat['recommandations']}
        self.assertIn('gbp_revendiquee', codes)
        self.assertEqual(codes['gbp_revendiquee']['severite'], 'critique')
        self.assertLess(resultat['dimensions']['fiche_google']['note'], 100)

    def test_page_sans_signal_local(self):
        html = page(corps="Nous réparons des drains.", titre="Débouchage de drain")
        resultat = note(html=html)
        page_locale_note = resultat['dimensions']['seo_local_page']
        self.assertLess(page_locale_note['note'], 50)
        self.assertIn('ville_titre',
                      {reco['code'] for reco in resultat['recommandations']})

    def test_balisage_local_absent(self):
        html = page(corps=CORPS_LOCAL, pied=PIED_LOCAL)
        resultat = note(html=html)
        schema = resultat['dimensions']['schema_local']
        self.assertEqual(schema['note'], 0)
        self.assertEqual(schema['verifications']['ignorees'], 2)

    def test_coherence_nap_reportee_dans_le_score(self):
        html = page_locale()
        nap = extract_nap(html)
        nap['coherence'] = compare_nap([
            {'source': 'Site', 'adresse': '1234, boul. Talbot, Chicoutimi, QC G7H 2B1'},
            {'source': 'Google', 'adresse': '1240, boul. Talbot, Chicoutimi, QC G7H 2B1'},
        ])
        avec = score_local_seo(extract_seo_signals(html), nap=nap)
        sans = note(html=html)
        self.assertLess(avec['dimensions']['nap_citations']['note'],
                        sans['dimensions']['nap_citations']['note'])
        self.assertIn('nap_coherent',
                      {reco['code'] for reco in avec['recommandations']})

    def test_recommandations_triees_par_points_recuperables(self):
        resultat = note()
        points = [reco['points_recuperables'] for reco in resultat['recommandations']]
        self.assertEqual(points, sorted(points, reverse=True))
        for reco in resultat['recommandations']:
            self.assertIn(reco['severite'], SEVERITES)
            self.assertTrue(reco['action'])

    def test_entrees_vides_ne_levent_rien(self):
        resultat = score_local_seo({})
        self.assertEqual(resultat['couverture'], 10.0)
        self.assertEqual(resultat['score'], 0)
        resultat = score_local_seo(None, nap=None, gbp=None, reviews=None)
        self.assertIsNotNone(resultat['dimensions'])


class DetectVerticalTests(SimpleTestCase):
    CAS = {
        'restauration': (
            "Notre menu du jour change chaque semaine. Réservez une table, "
            "apportez votre vin. Le chef propose un dessert maison et une "
            "terrasse ouverte tout l'été."
        ),
        'sante': (
            "Clinique dentaire familiale à Chicoutimi. Nettoyage dentaire, "
            "orthodontie et couronne dentaire. Prenez rendez-vous avec notre "
            "hygiéniste dentaire."
        ),
        'construction': (
            "Entrepreneur général avec licence RBQ. Rénovation de salle de bain, "
            "réfection de toiture et coulée de fondation. Soumission gratuite "
            "avant les travaux."
        ),
        'services_professionnels': (
            "Comptable CPA et fiscaliste. Tenue de livres, déclaration de revenus "
            "et états financiers pour votre entreprise."
        ),
        'commerce_detail': (
            "Boutique en ligne : ajoutez au panier et profitez de la livraison "
            "gratuite. Nos produits sont en stock en magasin et en succursale."
        ),
        'automobile': (
            "Garage automobile : changement d'huile, pneus d'hiver et inspection "
            "mécanique. Carrosserie, débosselage et remorquage disponibles."
        ),
    }

    def test_chaque_verticale_est_reconnue(self):
        for attendue, texte in self.CAS.items():
            resultat = detect_vertical(texte)
            self.assertEqual(resultat['verticale'], attendue, texte[:40])
            self.assertIn(resultat['confiance'], ('moyenne', 'elevee'))
            self.assertTrue(resultat['signaux'])

    def test_le_type_schema_accompagne_la_verticale(self):
        self.assertEqual(detect_vertical(self.CAS['restauration'])['type_schema'],
                         'Restaurant')
        self.assertEqual(detect_vertical(self.CAS['automobile'])['type_schema'],
                         'AutomotiveBusiness')

    def test_les_signaux_nomment_ce_qui_a_tranche(self):
        resultat = detect_vertical(self.CAS['automobile'])
        termes = {signal['terme'] for signal in resultat['signaux']}
        self.assertIn("changement d'huile", termes)
        forts = [signal for signal in resultat['signaux'] if signal['force'] == 'fort']
        self.assertTrue(forts)
        self.assertEqual(forts[0]['poids'], 3)

    def test_accents_et_majuscules_sans_effet(self):
        resultat = detect_vertical(
            "ÉBÉNISTERIE et CHARPENTE : rénovation complète, licence RBQ.")
        self.assertEqual(resultat['verticale'], 'construction')

    def test_texte_neutre(self):
        resultat = detect_vertical("Bonjour et bienvenue sur notre site web.")
        self.assertIsNone(resultat['verticale'])
        self.assertEqual(resultat['confiance'], 'aucune')
        self.assertEqual(resultat['score'], 0)
        self.assertEqual(resultat['signaux'], [])

    def test_vocabulaire_faible_seul_ne_tranche_pas(self):
        resultat = detect_vertical("Nos prix, nos marques et nos commandes.")
        self.assertNotEqual(resultat['confiance'], 'elevee')

    def test_les_candidats_sont_ordonnes(self):
        resultat = detect_vertical(
            self.CAS['construction'] + ' ' + self.CAS['restauration'])
        scores = [candidat['score'] for candidat in resultat['candidats']]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertGreaterEqual(len(resultat['candidats']), 2)

    def test_entrees_vides(self):
        for valeur in ('', None):
            self.assertIsNone(detect_vertical(valeur)['verticale'])
