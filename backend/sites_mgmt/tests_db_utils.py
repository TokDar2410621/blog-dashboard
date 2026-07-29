"""Tests for db_utils schema reconciliation on external client databases.

Bug fixe (incident 2026-07-20, 9 jours de panne) : la table blog_blogpost du
site client (QRStudio, site 5) portait published_at NOT NULL alors que le
modele Gridar permet NULL (drafts de generate_article). sync_blog_schema
n'ajoutait que les colonnes MANQUANTES et ne reconciliait jamais la
nullabilite : chaque draft finissait en IntegrityError 500, pour toujours.

Le chemin postgres reel n'est pas exerçable sur SQLite : on teste la fonction
extraite avec un cursor mocke et les vrais modeles blog. Run:
    python manage.py test sites_mgmt.tests_db_utils
"""
from unittest.mock import MagicMock

from django.apps import apps
from django.test import TestCase

from .db_utils import _drop_not_null_for_nullable_fields


class DropNotNullTests(TestCase):
    def setUp(self):
        self.model = apps.get_model('blog', 'BlogPost')
        self.cursor = MagicMock()

    def _executed_sql(self):
        return [c.args[0] for c in self.cursor.execute.call_args_list]

    def test_published_at_not_null_est_corrige(self):
        """La signature exacte de l'incident : published_at NOT NULL cote
        client + modele nullable -> DROP NOT NULL emis."""
        self.assertTrue(self.model._meta.get_field('published_at').null,
                        "precondition : le modele doit permettre NULL sur published_at")
        nullability = {'published_at': 'NO', 'title': 'NO', 'slug': 'NO'}
        _drop_not_null_for_nullable_fields(
            self.cursor, self.model, 'blog_blogpost', nullability, 'site_5')
        sql = self._executed_sql()
        self.assertIn(
            'ALTER TABLE "blog_blogpost" ALTER COLUMN "published_at" DROP NOT NULL', sql)

    def test_les_colonnes_non_nullables_du_modele_sont_intouchees(self):
        """title (null=False au modele) reste NOT NULL meme si la DB le porte :
        on n'affaiblit jamais une contrainte que le modele veut garder."""
        nullability = {'title': 'NO', 'slug': 'NO', 'content': 'NO'}
        _drop_not_null_for_nullable_fields(
            self.cursor, self.model, 'blog_blogpost', nullability, 'site_5')
        for stmt in self._executed_sql():
            self.assertNotIn('"title"', stmt)
            self.assertNotIn('"slug"', stmt)

    def test_deja_nullable_aucun_alter(self):
        """Schema deja conforme (published_at YES) : zero ALTER, idempotent."""
        nullability = {'published_at': 'YES', 'title': 'NO'}
        _drop_not_null_for_nullable_fields(
            self.cursor, self.model, 'blog_blogpost', nullability, 'site_5')
        self.assertEqual(self._executed_sql(), [])

    def test_colonne_absente_ignoree(self):
        """Une colonne du modele absente de la DB releve d'ADD COLUMN, pas de
        cette fonction : pas d'ALTER pour elle ici."""
        nullability = {}  # la DB ne connait aucune colonne
        _drop_not_null_for_nullable_fields(
            self.cursor, self.model, 'blog_blogpost', nullability, 'site_5')
        self.assertEqual(self._executed_sql(), [])

    def test_echec_alter_n_arrete_pas_les_suivants(self):
        """Un ALTER qui echoue (droits restreints) est loggue et n'empeche pas
        la reconciliation des autres colonnes."""
        nullable_cols = [f.column for f in self.model._meta.fields if f.null]
        self.assertGreaterEqual(len(nullable_cols), 2,
                                "precondition : il faut au moins 2 colonnes nullables au modele")
        nullability = {c: 'NO' for c in nullable_cols}
        self.cursor.execute.side_effect = [RuntimeError('permission denied')] + \
            [None] * (len(nullable_cols) - 1)
        _drop_not_null_for_nullable_fields(
            self.cursor, self.model, 'blog_blogpost', nullability, 'site_5')
        self.assertEqual(self.cursor.execute.call_count, len(nullable_cols))
