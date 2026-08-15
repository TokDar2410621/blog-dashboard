"""Tests for the standalone HTML report renderer.

Everything here is offline by construction: the module takes a dict and returns
a string, it opens no socket and touches no model. The document is checked with
`html.parser` rather than by substring where it matters, so an escaping hole
shows up as a real tag or a real attribute value, not as a hopeful `in` test.

Run all:
    python manage.py test sites_mgmt.tests_report_html
"""
from html.parser import HTMLParser

from django.test import SimpleTestCase

from .report_html import (
    LIBELLES_SEVERITES, SEVERITES, normalize_severite, render_report,
)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

_BALISES_VIDES = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
    'param', 'source', 'track', 'wbr',
})


class _Lecteur(HTMLParser):
    """Tag stack checker plus attribute and text collector.

    HTMLParser switches to CDATA mode inside <style>, so the stylesheet braces
    never reach the tag logic.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pile = []
        self.erreurs = []
        self.hrefs = []
        self.attributs = []
        self.balises = []
        self.textes = []

    def handle_starttag(self, tag, attrs):
        self.balises.append(tag)
        for cle, valeur in attrs:
            self.attributs.append((tag, cle, valeur or ''))
            if cle == 'href':
                self.hrefs.append(valeur or '')
        if tag not in _BALISES_VIDES:
            self.pile.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.balises.append(tag)
        for cle, valeur in attrs:
            self.attributs.append((tag, cle, valeur or ''))

    def handle_endtag(self, tag):
        if tag in _BALISES_VIDES:
            return
        if not self.pile:
            self.erreurs.append(f'</{tag}> sans ouverture')
            return
        if self.pile[-1] != tag:
            self.erreurs.append(f'</{tag}> ferme <{self.pile[-1]}>')
        self.pile.pop()

    def handle_data(self, data):
        if data.strip():
            self.textes.append(data)


def _lire(document: str) -> _Lecteur:
    lecteur = _Lecteur()
    lecteur.feed(document)
    lecteur.close()
    return lecteur


def _bloc_media_print(document: str) -> str:
    """Extract the @media print block by counting braces."""
    debut = document.find('@media print')
    if debut < 0:
        return ''
    ouvrante = document.find('{', debut)
    profondeur = 0
    for position in range(ouvrante, len(document)):
        if document[position] == '{':
            profondeur += 1
        elif document[position] == '}':
            profondeur -= 1
            if profondeur == 0:
                return document[ouvrante:position + 1]
    return ''


def _feuille_de_style(document: str) -> str:
    debut = document.find('<style>')
    fin = document.find('</style>')
    return document[debut + len('<style>'):fin] if debut >= 0 < fin else ''


RAPPORT_COMPLET = {
    'titre': 'Audit SEO de plomberie-laval.ca',
    'sous_titre': 'Analyse des 12 pages indexées',
    'date': '14 août 2026',
    'meta': {'Site': 'https://plomberie-laval.ca', 'Pages': 12},
    'resume': 'Le site perd du terrain sur les requêtes locales.',
    'score': {'valeur': 64, 'detail': 'Moyenne des 12 pages.'},
    'sections': [
        {
            'titre': 'Balises et métadonnées',
            'resume': 'État des titres et des descriptions.',
            'score': 72,
            'tableau': {
                'legende': 'Titres par page',
                'colonnes': ['Page', 'Titre', 'Longueur'],
                'lignes': [
                    ['/', 'Plombier à Laval', 17],
                    ['/urgence', 'Urgence 24h', {'valeur': 11, 'severite': 'critical'}],
                ],
            },
            'constats': [
                {'severite': 'warning', 'titre': 'Titre court',
                 'message': 'Le titre de /urgence fait 11 caractères.',
                 'avant': 'Urgence', 'apres': 'Urgence 24h'},
                {'severite': 'critical', 'titre': 'Description absente',
                 'message': 'Aucune meta description sur 4 pages.',
                 'details': ['/urgence', '/tarifs']},
                {'severite': 'ok', 'titre': 'Canonique',
                 'message': 'Toutes les pages ont une canonique.'},
            ],
            'recommandations': [
                {'texte': 'Réécrire les 4 descriptions manquantes.',
                 'priorite': 'high', 'effort': 'faible'},
                'Ajouter la ville dans le titre des pages de service.',
            ],
            'notes': ['Analyse basée sur le rendu HTML brut.'],
        },
        {
            'titre': 'Maillage interne',
            'constats': [{'severite': 'low', 'message': 'Trois pages orphelines.'}],
        },
    ],
    'pied': 'Rapport interne.',
}


# ---------------------------------------------------------------------------
# Severity vocabulary
# ---------------------------------------------------------------------------

class NormalizeSeveriteTests(SimpleTestCase):
    def test_vocabulaire_des_autres_modules(self):
        """Each delivered module spells severity differently; all must land."""
        attendu = {
            'critical': 'critique',     # drift_rules, gbp_lint
            'CRITICAL': 'critique',     # upstream drift_report
            'error': 'critique',        # schema_validator
            'hard_stop': 'critique',    # quality_gates
            'critique': 'critique',     # sxo
            'high': 'elevee',           # gbp_lint
            'elevee': 'elevee',         # sxo
            'élevée': 'elevee',
            'medium': 'moyenne',        # gbp_lint, schema_builder
            'warning': 'moyenne',       # drift_rules, quality_gates
            'moyenne': 'moyenne',       # sxo
            'low': 'faible',            # gbp_lint
            'faible': 'faible',         # sxo
            'info': 'info',             # drift_rules
            'ok': 'succes',             # quality_gates
            'aucune': 'succes',         # sxo
        }
        for brut, canonique in attendu.items():
            self.assertEqual(normalize_severite(brut), canonique, f'depuis {brut!r}')

    def test_inconnu_et_vide_deviennent_info(self):
        for brut in (None, '', '   ', 'zzz', 42, [], {}):
            self.assertEqual(normalize_severite(brut), 'info', f'depuis {brut!r}')

    def test_toutes_les_severites_ont_un_libelle(self):
        for severite in SEVERITES:
            self.assertIn(severite, LIBELLES_SEVERITES)


# ---------------------------------------------------------------------------
# Document shape
# ---------------------------------------------------------------------------

class StructureDocumentTests(SimpleTestCase):
    def setUp(self):
        self.document = render_report(RAPPORT_COMPLET)

    def test_document_complet(self):
        self.assertTrue(self.document.startswith('<!DOCTYPE html>'))
        self.assertIn('<html lang="fr">', self.document)
        self.assertIn('<meta charset="utf-8">', self.document)
        self.assertIn('name="viewport"', self.document)
        self.assertTrue(self.document.rstrip().endswith('</html>'))

    def test_balises_equilibrees(self):
        lecteur = _lire(self.document)
        self.assertEqual(lecteur.erreurs, [])
        self.assertEqual(lecteur.pile, [])

    def test_une_section_html_par_section_de_donnees(self):
        lecteur = _lire(self.document)
        self.assertEqual(lecteur.balises.count('section'), 2)

    def test_titre_et_sommaire(self):
        self.assertIn('<title>Audit SEO de plomberie-laval.ca | Gridar</title>',
                      self.document)
        self.assertIn('Sommaire', self.document)
        self.assertIn('href="#section-1"', self.document)
        self.assertIn('id="section-2"', self.document)

    def test_pas_de_sommaire_sous_deux_sections(self):
        document = render_report({'titre': 'Un seul bloc',
                                  'sections': [{'titre': 'Unique'}]})
        self.assertNotIn('Sommaire', document)

    def test_date_par_defaut_en_francais(self):
        document = render_report({'titre': 'Sans date'})
        self.assertIn('UTC', document)
        self.assertTrue(
            any(mois in document for mois in
                ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
                 'août', 'septembre', 'octobre', 'novembre', 'décembre')),
            'un mois francais doit apparaitre dans la date par defaut',
        )

    def test_sortie_en_francais(self):
        for mot in ('Recommandations', 'Critique', 'Priorité', 'Avant', 'Après',
                    'Enregistrer en PDF'):
            self.assertIn(mot, self.document)

    def test_rapport_non_indexable(self):
        self.assertIn('name="robots" content="noindex, nofollow"', self.document)


# ---------------------------------------------------------------------------
# Escaping
# ---------------------------------------------------------------------------

class EchappementTests(SimpleTestCase):
    """A client article title can contain anything, markup included."""

    CHARGE = '<script>alert("xss")</script>'

    def setUp(self):
        self.document = render_report({
            'titre': self.CHARGE,
            'sous_titre': self.CHARGE,
            'marque': self.CHARGE,
            'resume': self.CHARGE,
            'meta': {self.CHARGE: self.CHARGE},
            'pied': self.CHARGE,
            'sections': [{
                'titre': self.CHARGE,
                'resume': self.CHARGE,
                'tableau': {
                    'legende': self.CHARGE,
                    'colonnes': [self.CHARGE],
                    'lignes': [[self.CHARGE], [{'valeur': self.CHARGE,
                                                'severite': 'critical'}]],
                },
                'constats': [{
                    'severite': self.CHARGE,
                    'titre': self.CHARGE,
                    'message': self.CHARGE,
                    'details': [self.CHARGE],
                    'avant': self.CHARGE,
                    'apres': self.CHARGE,
                    'correctif': self.CHARGE,
                }],
                'recommandations': [{'texte': self.CHARGE, 'priorite': self.CHARGE,
                                     'detail': self.CHARGE, 'effort': self.CHARGE}],
                'notes': [self.CHARGE],
            }],
        })

    def test_aucune_balise_injectee(self):
        self.assertNotIn('<script>', self.document)
        self.assertNotIn('</script>', self.document)
        self.assertIn('&lt;script&gt;', self.document)

    def test_le_parseur_ne_voit_aucun_script(self):
        lecteur = _lire(self.document)
        self.assertNotIn('script', lecteur.balises)
        self.assertEqual(lecteur.erreurs, [])
        self.assertEqual(lecteur.pile, [])

    def test_le_texte_original_est_restitue_intact(self):
        lecteur = _lire(self.document)
        joints = ' '.join(lecteur.textes)
        self.assertIn(self.CHARGE, joints)

    def test_attribut_ne_peut_pas_sortir_de_ses_guillemets(self):
        charge = 'x" onmouseover="alert(1)'
        document = render_report({
            'titre': charge,
            'sections': [{'titre': charge,
                          'tableau': {'legende': charge, 'colonnes': ['a'],
                                      'lignes': [['b']]}}],
        })
        lecteur = _lire(document)
        self.assertNotIn(
            'onmouseover', [cle for _, cle, _ in lecteur.attributs],
        )
        aria = [valeur for _, cle, valeur in lecteur.attributs if cle == 'aria-label']
        self.assertIn(charge, aria)

    def test_les_apostrophes_restent_lisibles(self):
        document = render_report({'titre': "L'état d'un site"})
        self.assertIn("L'état d'un site", document)


class LiensTests(SimpleTestCase):
    """Only http(s) ever reaches an href."""

    def _hrefs(self, document):
        return _lire(document).hrefs

    def test_schemas_dangereux_refuses(self):
        for dangereux in (
            'javascript:alert(1)',
            'JavaScript:alert(1)',
            'java\nscript:alert(1)',
            'data:text/html;base64,PHNjcmlwdD4=',
            'file:///etc/passwd',
            '//evil.example.com/',
            'vbscript:msgbox(1)',
        ):
            document = render_report({
                'titre': 'Liens',
                'meta': {'Site': dangereux},
                'sections': [{
                    'titre': 'S',
                    'constats': [{'message': 'm', 'url': dangereux}],
                    'recommandations': [{'texte': 't', 'url': dangereux}],
                    'tableau': {'colonnes': ['u'],
                                'lignes': [[{'valeur': 'clic', 'url': dangereux}]]},
                }],
            })
            for href in self._hrefs(document):
                self.assertTrue(
                    href.startswith('#') or href.lower().startswith('http'),
                    f'href interdit rendu pour {dangereux!r} : {href!r}',
                )
            self.assertNotIn('href="javascript', document.lower())
            self.assertNotIn('href="data:', document.lower())

    def test_url_http_devient_un_lien(self):
        document = render_report({
            'titre': 'Liens',
            'sections': [{'titre': 'S',
                          'constats': [{'message': 'm',
                                        'url': 'https://gridar.app/page?a=1&b=2'}]}],
        })
        self.assertIn('https://gridar.app/page?a=1&amp;b=2', document)
        self.assertIn('rel="noopener noreferrer"', document)
        self.assertIn('https://gridar.app/page?a=1&b=2', self._hrefs(document))


# ---------------------------------------------------------------------------
# Long dashes
# ---------------------------------------------------------------------------

class TiretsLongsTests(SimpleTestCase):
    """Codepoints are written as escapes so no source line carries one either."""

    EM = '\u2014'      # em dash
    EN = '\u2013'      # en dash
    BARRE = '\u2015'   # horizontal bar
    MOINS = '\u2212'   # minus sign

    def test_aucun_tiret_cadratin_dans_la_sortie(self):
        sale = (f'Titre {self.EM} suite {self.EN} fin {self.BARRE} reste '
                f'{self.MOINS} signe')
        document = render_report({
            'titre': sale,
            'sous_titre': sale,
            'resume': sale,
            'meta': {sale: sale},
            'pied': sale,
            'sections': [{
                'titre': sale,
                'resume': sale,
                'score': {'valeur': 50, 'libelle': sale, 'detail': sale},
                'tableau': {'legende': sale, 'colonnes': [sale], 'lignes': [[sale]]},
                'constats': [{'titre': sale, 'message': sale, 'details': [sale],
                              'avant': sale, 'apres': sale, 'correctif': sale}],
                'recommandations': [{'texte': sale, 'detail': sale, 'effort': sale}],
                'notes': [sale],
            }],
        })
        for interdit in (self.EM, self.EN, self.BARRE, self.MOINS):
            self.assertNotIn(interdit, document,
                             f'tiret long {interdit!r} present dans le HTML')
        self.assertIn('Titre - suite - fin - reste - signe', document)

    def test_rapport_ordinaire_sans_tiret_long(self):
        document = render_report(RAPPORT_COMPLET)
        for interdit in (self.EM, self.EN):
            self.assertNotIn(interdit, document)


# ---------------------------------------------------------------------------
# Self-contained document
# ---------------------------------------------------------------------------

class AutonomieTests(SimpleTestCase):
    def setUp(self):
        self.document = render_report(RAPPORT_COMPLET)

    def test_aucune_ressource_externe(self):
        minuscule = self.document.lower()
        for interdit in ('<script', '<link', 'src=', '@import', 'url(',
                         'fonts.googleapis', 'cdn.', '.woff', '.css"'):
            self.assertNotIn(interdit, minuscule, f'ressource externe : {interdit}')

    def test_aucun_gestionnaire_inline(self):
        """A CSP that forbids inline handlers must not break the document."""
        minuscule = self.document.lower()
        for interdit in ('onclick', 'onload', 'onerror', 'javascript:'):
            self.assertNotIn(interdit, minuscule)

    def test_css_inline_unique(self):
        self.assertEqual(self.document.count('<style>'), 1)
        self.assertGreater(len(_feuille_de_style(self.document)), 2000)

    def test_polices_systeme_seulement(self):
        feuille = _feuille_de_style(self.document)
        self.assertIn('sans-serif', feuille)
        self.assertNotIn('@font-face', feuille)

    def test_les_couleurs_vivent_dans_des_classes(self):
        """Upstream inlined every colour, which no print rule can override.

        The only inline style left carries the gauge width, one per score block,
        and the sample report has two scores.
        """
        self.assertEqual(self.document.count('style="'), 2)
        self.assertEqual(self.document.count('style="width:'), 2)
        self.assertIn('class="constat sev-critique"', self.document)


# ---------------------------------------------------------------------------
# Print stylesheet
# ---------------------------------------------------------------------------

class ImpressionTests(SimpleTestCase):
    def setUp(self):
        self.document = render_report(RAPPORT_COMPLET)
        self.impression = _bloc_media_print(self.document)

    def test_bloc_media_print_present_et_ferme(self):
        self.assertTrue(self.impression.startswith('{'))
        self.assertTrue(self.impression.endswith('}'))
        self.assertEqual(self.impression.count('{'), self.impression.count('}'))

    def test_fond_blanc_et_texte_fonce(self):
        self.assertIn('--fond: #ffffff;', self.impression)
        self.assertIn('--fond-carte: #ffffff;', self.impression)
        self.assertIn('background: #ffffff;', self.impression)
        self.assertIn('--texte: #111111;', self.impression)

    def test_chrome_masque(self):
        self.assertIn('.no-print { display: none !important; }', self.impression)
        self.assertIn('class="barre no-print"', self.document)

    def test_couleurs_semantiques_foncees(self):
        """Emerald, amber and red at screen tint are unreadable on paper."""
        ecran = _feuille_de_style(self.document).split('@media print')[0]
        for jeton in ('--critique', '--elevee', '--moyenne', '--succes', '--info',
                      '--faible'):
            ligne_ecran = self._valeur(ecran, jeton)
            ligne_print = self._valeur(self.impression, jeton)
            self.assertTrue(ligne_ecran and ligne_print, f'{jeton} defini deux fois')
            self.assertNotEqual(ligne_ecran, ligne_print,
                                f'{jeton} non foncé pour le papier')
            self.assertLess(self._luminance(ligne_print), self._luminance(ligne_ecran),
                            f'{jeton} doit etre plus sombre a l impression')

    def test_teintes_de_fond_neutralisees(self):
        for jeton in ('--fond-critique', '--fond-moyenne', '--fond-succes'):
            self.assertEqual(self._valeur(self.impression, jeton), '#ffffff')

    def test_entete_ne_reste_pas_un_aplat(self):
        """A navy header with white text prints as invisible text."""
        self.assertIn('.entete {', self.impression)
        entete = self.impression.split('.entete {', 1)[1].split('}', 1)[0]
        self.assertIn('background: #ffffff;', entete)

    def test_tableaux_ne_sont_pas_coupes(self):
        self.assertIn('.tableau-defilant { overflow: visible; }', self.impression)

    def test_coupures_de_page(self):
        self.assertIn('break-inside: avoid', self.impression)
        self.assertIn('@page { margin: 15mm; }', self.impression)

    def test_url_revelees_sur_papier(self):
        self.assertIn('attr(href)', self.impression)

    @staticmethod
    def _valeur(css: str, jeton: str) -> str:
        for ligne in css.splitlines():
            nettoyee = ligne.strip()
            if nettoyee.startswith(jeton + ':'):
                return nettoyee.split(':', 1)[1].strip().rstrip(';')
        return ''

    @staticmethod
    def _luminance(couleur: str) -> float:
        couleur = couleur.strip().lstrip('#')
        if len(couleur) != 6:
            return 1.0
        r, v, b = (int(couleur[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * r + 0.7152 * v + 0.0722 * b


# ---------------------------------------------------------------------------
# Responsive
# ---------------------------------------------------------------------------

class ResponsiveTests(SimpleTestCase):
    def setUp(self):
        self.feuille = _feuille_de_style(render_report(RAPPORT_COMPLET))

    def test_tableau_defile_dans_son_conteneur(self):
        self.assertIn('.tableau-defilant {', self.feuille)
        conteneur = self.feuille.split('.tableau-defilant {', 1)[1].split('}', 1)[0]
        self.assertIn('overflow-x: auto;', conteneur)

    def test_le_tableau_deborde_avant_de_comprimer_les_colonnes(self):
        self.assertIn('min-width: 34rem;', self.feuille)

    def test_requete_media_etroite(self):
        self.assertIn('@media (max-width: 40rem)', self.feuille)

    def test_grilles_fluides(self):
        self.assertIn('repeat(auto-fit, minmax(', self.feuille)


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

class ScoreTests(SimpleTestCase):
    def _score(self, valeur):
        return render_report({'titre': 't', 'score': valeur})

    def test_score_simple(self):
        document = self._score(64)
        self.assertIn('>64<', document)
        self.assertIn('style="width:64%"', document)
        self.assertIn('sev-moyenne', document)

    def test_largeur_bornee(self):
        self.assertIn('style="width:100%"', self._score(250))
        self.assertIn('style="width:0%"', self._score(-40))

    def test_paliers(self):
        self.assertIn('Solide', self._score(92))
        self.assertIn('Correct', self._score(70))
        self.assertIn('À améliorer', self._score(45))
        self.assertIn('Critique', self._score(12))

    def test_ratio_flottant_converti(self):
        document = self._score(0.87)
        self.assertIn('>87<', document)
        self.assertIn('>/100<', document)

    def test_entier_un_reste_un_point(self):
        document = self._score(1)
        self.assertIn('>1<', document)
        self.assertIn('style="width:1%"', document)

    def test_base_personnalisee(self):
        document = self._score({'valeur': 8.5, 'sur': 10, 'libelle': 'Bon'})
        self.assertIn('>8,5<', document)
        self.assertIn('>/10<', document)
        self.assertIn('style="width:85%"', document)

    def test_score_invalide_ignore(self):
        for mauvais in ('abc', None, {}, [1, 2]):
            document = render_report({'titre': 't', 'score': mauvais})
            self.assertNotIn('class="score ', document)


class TableauTests(SimpleTestCase):
    def test_lignes_en_listes(self):
        document = render_report({'titre': 't', 'sections': [{'tableau': {
            'colonnes': ['Page', 'Score'], 'lignes': [['/', 80], ['/a', 40]],
        }}]})
        lecteur = _lire(document)
        self.assertEqual(lecteur.balises.count('th'), 2)
        self.assertEqual(lecteur.balises.count('td'), 4)

    def test_lignes_en_dictionnaires_sans_colonnes_declarees(self):
        document = render_report({'titre': 't', 'sections': [{'tableau': {
            'lignes': [{'Page': '/', 'Mots': 820}, {'Page': '/a', 'Mots': 120}],
        }}]})
        self.assertIn('<th scope="col">Page</th>', document)
        self.assertIn('<th scope="col">Mots</th>', document)
        self.assertIn('<td>820</td>', document)

    def test_ligne_trop_courte_est_completee(self):
        document = render_report({'titre': 't', 'sections': [{'tableau': {
            'colonnes': ['a', 'b', 'c'], 'lignes': [['1']],
        }}]})
        lecteur = _lire(document)
        self.assertEqual(lecteur.balises.count('td'), 3)
        self.assertEqual(lecteur.erreurs, [])

    def test_cellule_avec_severite(self):
        document = render_report({'titre': 't', 'sections': [{'tableau': {
            'colonnes': ['Etat'],
            'lignes': [[{'valeur': 'Manquant', 'severite': 'critical'}]],
        }}]})
        self.assertIn('<span class="pastille sev-critique">Manquant</span>', document)

    def test_troncature_des_grands_tableaux(self):
        document = render_report({'titre': 't', 'sections': [{'tableau': {
            'colonnes': ['n'], 'lignes': [[i] for i in range(500)],
        }}]})
        self.assertIn('Affichage limité aux 400 premières lignes sur 500', document)
        lecteur = _lire(document)
        self.assertEqual(lecteur.balises.count('td'), 400)

    def test_tableau_en_liste_simple(self):
        document = render_report({'titre': 't',
                                  'sections': [{'tableau': [['a', 'b']]}]})
        self.assertIn('<td>a</td>', document)


class ConstatsTests(SimpleTestCase):
    def test_tri_par_severite(self):
        document = render_report({'titre': 't', 'sections': [{'constats': [
            {'severite': 'low', 'message': 'basse'},
            {'severite': 'critical', 'message': 'haute'},
            {'severite': 'medium', 'message': 'milieu'},
        ]}]})
        self.assertLess(document.index('haute'), document.index('milieu'))
        self.assertLess(document.index('milieu'), document.index('basse'))

    def test_bilan_compte_les_severites(self):
        document = render_report(RAPPORT_COMPLET)
        bilan = document.split('class="bilan"', 1)[1].split('</div></div>', 1)[0]
        self.assertIn('sev-critique', bilan)
        self.assertIn('>1<', bilan)

    def test_constat_en_chaine_simple(self):
        document = render_report({'titre': 't',
                                  'sections': [{'constats': ['Rien à signaler']}]})
        self.assertIn('Rien à signaler', document)
        self.assertIn('sev-info', document)

    def test_avant_apres(self):
        document = render_report({'titre': 't', 'sections': [{'constats': [
            {'severite': 'warning', 'message': 'm', 'avant': 'ancien', 'apres': ''},
        ]}]})
        self.assertIn('Avant', document)
        self.assertIn('ancien', document)
        self.assertIn('(vide)', document)

    def test_troncature_des_constats(self):
        document = render_report({'titre': 't', 'sections': [{'constats': [
            {'severite': 'low', 'message': f'c{i}'} for i in range(320)
        ] + [{'severite': 'critical', 'message': 'la pire'}]}]})
        self.assertIn('321 constats au total, 300 affichés.', document)
        self.assertIn('la pire', document)

    def test_recommandations_avec_priorite(self):
        document = render_report({'titre': 't', 'sections': [{'recommandations': [
            {'texte': 'Corriger les titres', 'priorite': 'critical'},
        ]}]})
        self.assertIn('Priorité critique', document)
        self.assertIn('Corriger les titres', document)


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

class RobustesseTests(SimpleTestCase):
    def test_rapport_vide(self):
        document = render_report({})
        lecteur = _lire(document)
        self.assertEqual(lecteur.erreurs, [])
        self.assertEqual(lecteur.pile, [])
        self.assertIn('Rapport SEO', document)

    def test_entree_non_dict(self):
        for mauvais in (None, [], 'texte', 42):
            document = render_report(mauvais)
            self.assertTrue(document.startswith('<!DOCTYPE html>'))
            self.assertEqual(_lire(document).erreurs, [])

    def test_valeurs_de_types_inattendus(self):
        class Objet:
            def __str__(self):
                return 'objet <b>brut</b>'

        document = render_report({
            'titre': Objet(),
            'meta': [('Tags', {'a', 'b'})],
            'sections': [{
                'titre': ['liste', 'de', 'titres'],
                'constats': [{'severite': 3, 'message': {'cle': 'valeur'},
                              'details': (1, 2, 3)}],
                'tableau': {'colonnes': [None], 'lignes': [[None], [{'x': 1}]]},
                'notes': 'une note unique',
            }],
        })
        lecteur = _lire(document)
        self.assertEqual(lecteur.erreurs, [])
        self.assertEqual(lecteur.pile, [])
        self.assertIn('objet &lt;b&gt;brut&lt;/b&gt;', document)
        self.assertIn('une note unique', document)

    def test_texte_tres_long_tronque(self):
        document = render_report({'titre': 't', 'sections': [
            {'constats': [{'message': 'x' * 20000}]},
        ]})
        self.assertLess(len(document), 60000)
        self.assertIn('…', document)

    def test_nombre_de_sections_borne(self):
        document = render_report({'titre': 't',
                                  'sections': [{'titre': f's{i}'} for i in range(200)]})
        self.assertEqual(_lire(document).balises.count('section'), 60)

    def test_rendu_deterministe(self):
        self.assertEqual(render_report(RAPPORT_COMPLET),
                         render_report(RAPPORT_COMPLET))
