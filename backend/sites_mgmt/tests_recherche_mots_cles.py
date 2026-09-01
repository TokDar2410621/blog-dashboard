"""Tests : intention et familles de variantes de KeywordResearchView.

Contexte du 2026-09-01. Cette vue n'avait aucun test, sur 41 fichiers de tests
dans le module, et deux defauts y vivaient depuis longtemps.

Le premier : les jetons accentues des tables d'intention etaient du mojibake
double-encode. Le fichier contenait litteralement 'coA»t' la ou il fallait
'cout' avec accent circonflexe. Consequence mesuree via gridar_audit_article
puis via l'outil MCP : seule l'orthographe SANS accent etait reconnue, alors
que Serper et Gemini rendent du francais accentue. Un produit vendu au Quebec
classait donc mal precisement les requetes ecrites correctement.

Le second : le dedoublonnage comparait des chaines exactes. Sur le seed
"sablage de plancher montreal", trois formulations de la meme demande de prix
sortaient comme trois lignes sans lien. Elles sont maintenant reliees par une
famille, pas fusionnees : un mot-cle efface est invisible, un doublon reste
sous les yeux et se juge.

Tout est hors ligne : ces methodes ne font ni reseau ni base de donnees.

Run: python manage.py test sites_mgmt.tests_recherche_mots_cles
"""
from django.test import SimpleTestCase

from .views import KeywordResearchView


def vue():
    return KeywordResearchView()


def regrouper(mots, source='serper_related'):
    """Passe une liste de libelles au regroupement et rend les items enrichis."""
    items = [
        {'keyword': m, 'source': source} if isinstance(m, str)
        else {'keyword': m[0], 'source': m[1]}
        for m in mots
    ]
    vue()._regrouper(items)
    return items


def familles(items):
    return len({i['family_id'] for i in items})


# Les 22 mots-cles reellement rendus par l'outil le 2026-09-01, seed
# "sablage de plancher montreal", language 'fr'. Ils servent de reference
# parce qu'ils viennent d'un appel reel, pas d'un echantillon invente.
RUN_REEL = [
    ('Sablage de plancher Montréal prix', 'serper_related'),
    ('Sablage de plancher montreal address', 'serper_related'),
    ('Sablage de plancher prix', 'serper_related'),
    ('Sablage de plancher prix pied carré', 'serper_related'),
    ('Sablage de plancher sans poussière prix', 'serper_related'),
    ('Sablage de plancher Rive-Sud', 'serper_related'),
    ('Sablage de plancher pas cher', 'serper_related'),
    ('Sablage de plancher Terrebonne', 'serper_related'),
    ('Est-il possible de sabler soi-même un plancher ?', 'serper_paa'),
    ('Quelle est la meilleure sableuse à plancher sans poussière ?', 'serper_paa'),
    ("Combien coûte le sablage d'un escalier ?", 'serper_paa'),
    ("Qu'est-ce que le sablage de plancher en parqueterie ?", 'serper_paa'),
    ('prix sablage de plancher montreal', 'gemini_longtail'),
    ('combien coute sablage plancher montreal', 'gemini_longtail'),
    ('sablage plancher sans poussiere montreal', 'gemini_longtail'),
    ('sablage et vernissage plancher montreal', 'gemini_longtail'),
    ('meilleure compagnie sablage plancher montreal', 'gemini_longtail'),
    ('sablage plancher bois franc montreal', 'gemini_longtail'),
    ('comment trouver sableur plancher montreal', 'gemini_longtail'),
    ('sablage de plancher residentiel montreal', 'gemini_longtail'),
    ('quel prix pour sablage plancher montreal', 'gemini_longtail'),
    ('sablage de plancher commercial montreal', 'gemini_longtail'),
]


class IntentionAccentueeTests(SimpleTestCase):
    """Le francais correct doit etre reconnu aussi bien que le francais tape vite.

    C'est le test qui echouait avant la reparation de l'encodage : la colonne
    de droite rendait 'informational' pour chaque ligne.
    """

    def test_les_deux_orthographes_donnent_la_meme_intention(self):
        for sans, avec, attendu in [
            ("combien coute le sablage", "combien coûte le sablage", 'commercial'),
            ("telecharger le guide", "télécharger le guide", 'transactional'),
            ("reserver un sablage", "réserver un sablage", 'transactional'),
        ]:
            self.assertEqual(vue()._estimate_intent(sans), attendu, sans)
            self.assertEqual(vue()._estimate_intent(avec), attendu, avec)

    def test_le_mot_cle_accentue_du_run_reel_est_commercial(self):
        # Rendu 'informational' par la production avant ce correctif.
        self.assertEqual(
            vue()._estimate_intent("Combien coûte le sablage d'un escalier ?"),
            'commercial',
        )

    def test_aucun_jeton_des_tables_ne_porte_de_mojibake(self):
        """Garde mecanique : c'est ce controle qui manquait.

        'Ã' ne peut apparaitre dans un jeton francais correct ; sa presence
        signale des octets UTF-8 relus en Latin-1.
        """
        tables = (
            KeywordResearchView.COMMERCIAL_TOKENS,
            KeywordResearchView.TRANSACTIONAL_TOKENS,
            KeywordResearchView.NAVIGATIONAL_TOKENS,
            KeywordResearchView.INFORMATIONAL_TOKENS,
        )
        for table in tables:
            for jeton in table:
                self.assertNotIn('Ã', jeton, jeton)
                self.assertNotIn('â€', jeton, jeton)


class FamillesDeVariantesTests(SimpleTestCase):
    def test_le_run_reel_ne_perd_aucun_mot_cle(self):
        items = regrouper(RUN_REEL)

        self.assertEqual(len(items), 22)
        self.assertEqual(familles(items), 20)

    def test_les_formulations_de_prix_forment_une_famille(self):
        items = regrouper(RUN_REEL)
        groupes = [i for i in items if i['family_size'] > 1]
        libelles = {i['keyword'] for i in groupes}

        self.assertEqual(libelles, {
            'Sablage de plancher Montréal prix',
            'prix sablage de plancher montreal',
            'quel prix pour sablage plancher montreal',
        })

    def test_le_representant_vient_de_serper_pas_de_gemini(self):
        """Serper lit un vrai SERP, Gemini genere. Le libelle montre gagne."""
        items = regrouper(RUN_REEL)
        primaire = [i for i in items if i['family_size'] > 1 and i['family_primary']]

        self.assertEqual(len(primaire), 1)
        self.assertEqual(primaire[0]['source'], 'serper_related')

    def test_les_questions_paa_sortent_intactes(self):
        items = regrouper(RUN_REEL)
        questions = [i for i in items if i['source'] == 'serper_paa']

        self.assertEqual(len(questions), 4)
        for q in questions:
            # Rendues octet pour octet : ce sont des titres de section prets
            # a l'emploi, la ponctuation en fait partie.
            self.assertTrue(q['keyword'].endswith('?'))
            self.assertEqual(q['family_size'], 1)

    def test_family_size_vaut_toujours_un_quand_rien_ne_se_repete(self):
        """Le champ est present meme seul : c'est une mesure, pas un silence."""
        items = regrouper(['sablage plancher montreal'])

        self.assertEqual(items[0]['family_size'], 1)
        self.assertTrue(items[0]['family_primary'])


class GardesDuRegroupementTests(SimpleTestCase):
    """Chaque garde ici a coute un jeton retire de _MOTS_OUTILS.

    Elles disent ce que le regroupement ne doit JAMAIS rapprocher. Un echec
    ici veut dire qu'un mot-cle a ete range sous une famille qui n'est pas la
    sienne.
    """

    def test_une_relation_spatiale_reste_porteuse(self):
        # Avec 'sur' dans les mots-outils, les deux premiers fusionnaient
        # pendant que 'sous' restait porteur. L'asymetrie fabriquait une
        # famille fausse.
        items = regrouper([
            'isolation sur plancher', 'isolation plancher', 'isolation sous plancher',
        ])

        self.assertEqual(familles(items), 3)

    def test_les_mots_interrogatifs_qui_portent_l_intention_restent(self):
        # 'comment' et 'pourquoi' sont exactement ce que _estimate_intent lit
        # pour rendre 'informational'. Les effacer melangerait deux intentions
        # sous un seul representant.
        items = regrouper([
            'comment sabler un plancher', 'sabler un plancher', 'pourquoi sabler plancher',
        ])

        self.assertEqual(familles(items), 3)

    def test_la_negation_reste_porteuse(self):
        # Deux devis differents.
        items = regrouper(['sablage sans poussiere', 'sablage poussiere'])

        self.assertEqual(familles(items), 2)

    def test_deux_villes_sont_deux_pages(self):
        # Coeur du SEO local : egalite stricte d'ensembles, aucun seuil.
        items = regrouper([
            'Sablage de plancher Terrebonne',
            'Sablage de plancher Rive-Sud',
            'Sablage de plancher Montréal prix',
        ])

        self.assertEqual(familles(items), 3)

    def test_deux_verticales_voisines_restent_separees(self):
        items = regrouper([
            'sablage de plancher residentiel montreal',
            'sablage de plancher commercial montreal',
        ])

        self.assertEqual(familles(items), 2)

    def test_une_chaine_sans_mot_porteur_reste_seule(self):
        # Sans cle sentinelle, toutes les chaines faites de mots-outils
        # tomberaient dans une meme famille fourre-tout.
        items = regrouper(['de la', 'le des', 'Pourquoi ?'])

        self.assertEqual(familles(items), 3)

    def test_le_synonyme_de_prix_reste_dehors_et_c_est_voulu(self):
        """Garde-fou, pas objectif.

        "combien coute" et "prix" disent la meme chose, et aucune
        normalisation de chaine ne franchit cet ecart. Le rapprocher exigerait
        d'enumerer les facons de demander un prix en francais quebecois, un
        ensemble qui n'a pas de fin. Si ce test passe au vert un jour, c'est
        qu'une telle table a ete ecrite.
        """
        items = regrouper([
            'Sablage de plancher Montréal prix',
            'combien coute sablage plancher montreal',
        ])

        self.assertEqual(familles(items), 2)
