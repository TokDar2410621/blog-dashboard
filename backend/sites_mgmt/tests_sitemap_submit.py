"""Tests : re-soumission de sitemap a Search Console (scope d'ecriture).

Contexte : le scope OAuth etait `webmasters.readonly`, donc `sitemaps.submit`
etait interdit et re-soumettre un sitemap restait un geste manuel. Constate le
2026-08-02 sur gridar.app (sitemap corrige vers le host www, jamais relu par
Google) et qrstudio.agency (telecharge une seule fois le 14/07, 0 URL indexee
sur 80). Le scope passe a `webmasters` complet ; les jetons emis AVANT restent
en lecture seule, et ce cas doit se dire clairement au lieu d'echouer sec.

Les classes couvrent aussi les cinq defauts trouves par la revue adversariale
du 2026-08-03 : bruit de log sur les jetons anciens, sitemap hors propriete,
jeton revoque mal classe, detection par sous-chaine (un domaine contenant
« scope » declenchait un faux « reconnecte »), et la doc client devenue fausse.

Hermetique : le client Google est simule au niveau de _build_gsc_service, aucun
reseau. Tourne avec ou sans googleapiclient installe ; quand la lib est la
(backend/venv), les erreurs simulees sont de VRAIS HttpError.
Run: python manage.py test sites_mgmt.tests_sitemap_submit
"""
import ast
import io
import os
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from . import proof_loop
from .api_v1 import V1SitemapSubmitView
from .models import Site

User = get_user_model()

def _http_error_cls():
    """La vraie HttpError si la lib est la, sinon None. Import PARESSEUX : un
    import au chargement du module ferait entrer googleapiclient dans
    sys.modules des la decouverte des tests, et tests_gsc_property remplace ce
    module par un faux via patch.dict(sys.modules) : au demontage, patch.dict
    vide le dict et le restaure, ce qui EVINCE les modules importes entre-temps.
    Les classes reimportees ensuite ne sont plus les memes objets, et
    googleapiclient rejette alors des Credentials pourtant valides
    (« 'Credentials' object has no attribute 'authorize' », 42 fois)."""
    try:
        from googleapiclient.errors import HttpError
        return HttpError
    except ImportError:
        return None


def _refresh_error_cls():
    try:
        from google.auth.exceptions import RefreshError
        return RefreshError
    except ImportError:
        return None


class _FauxReponse:
    def __init__(self, status):
        self.status = status
        self.reason = ''


class _FauxHttpError(Exception):
    """Meme surface que googleapiclient.errors.HttpError : .resp.status,
    .error_details, .reason, et un str() qui contient l'URI appelee."""

    def __init__(self, status, details, uri, reason=''):
        self.resp = _FauxReponse(status)
        self.error_details = details
        self.reason = reason
        self.uri = uri
        super().__init__('<HttpError %s when requesting %s>' % (status, uri))

    def __str__(self):
        return '<HttpError %s when requesting %s returned "%s">' % (
            self.resp.status, self.uri, self.reason)


def erreur_http(status, details, uri, reason=''):
    """Une erreur Google. Vraie HttpError si la lib est installee (c'est la
    forme que la prod verra), sinon un jumeau fidele."""
    cls = _http_error_cls()
    if cls is None:
        return _FauxHttpError(status, details, uri, reason)
    import json as _json
    contenu = _json.dumps({'error': {'code': status, 'message': reason,
                                     'errors': details, 'status': reason}}).encode()
    err = cls(_FauxReponse(status), contenu, uri=uri)
    err.error_details = details
    err.reason = reason
    return err


def erreur_refresh():
    """Jeton revoque ou expire. google-auth leve RefreshError, pas HttpError."""
    cls = _refresh_error_cls()
    if cls is None:
        class _FauxRefreshError(Exception):
            pass
        return _FauxRefreshError(
            "('invalid_grant: Token has been expired or revoked.', {})")
    return cls('invalid_grant: Token has been expired or revoked.',
               {'error': 'invalid_grant'})


URI_GRIDAR = ('https://searchconsole.googleapis.com/webmasters/v3/sites/'
              'https%3A%2F%2Fwww.gridar.app%2F/sitemaps/'
              'https%3A%2F%2Fwww.gridar.app%2Fsitemap.xml')

ERR_SCOPE = lambda: erreur_http(
    403, [{'message': 'Insufficient Permission', 'domain': 'global',
           'reason': 'insufficientPermissions'}],
    URI_GRIDAR, reason='Request had insufficient authentication scopes.')

ERR_PAS_PROPRIETAIRE = lambda: erreur_http(
    403, [{'message': "User does not have sufficient permission for site "
                      "'https://gridar.app/'.", 'reason': 'forbidden'}],
    URI_GRIDAR, reason="User does not have sufficient permission for site.")

ERR_INTROUVABLE = lambda: erreur_http(
    404, [{'message': 'Not Found', 'reason': 'notFound'}], URI_GRIDAR,
    reason='Not Found')


def _service(entries=None):
    """Client GSC simule : submit() reussit, sites().list() rend `entries`."""
    svc = MagicMock()
    svc.sitemaps.return_value.submit.return_value.execute.return_value = {}
    svc.sites.return_value.list.return_value.execute.return_value = {
        'siteEntry': [{'siteUrl': u, 'permissionLevel': 'siteOwner'}
                      for u in (entries or [])]}
    return svc


class ScopeEcritureTests(TestCase):
    """Garde-fou de regression : le scope demande DOIT autoriser l'ecriture.
    Un retour a `.readonly` reintroduirait le bug en silence (la lecture
    continuerait de marcher, seule la soumission casserait)."""

    def test_proof_loop_demande_le_scope_ecriture(self):
        self.assertEqual(proof_loop.GSC_SCOPES,
                         ['https://www.googleapis.com/auth/webmasters'])

    def test_views_demande_le_meme_scope(self):
        """views.py porte SA propre constante (c'est elle qui pilote le consentement
        OAuth). Les deux divergeaient = jeton lecture seule malgre proof_loop."""
        from . import views
        self.assertEqual(views.GSC_SCOPES, proof_loop.GSC_SCOPES)


class PasDeScopesSurLesCredentialsTests(TestCase):
    """Aucune reconstruction de Credentials ne doit passer scopes=.

    Le scope d'un refresh token vient du consentement ; le passer au client ne
    l'elargit pas, il sert de reference de comparaison a google-auth. Depuis que
    GSC_SCOPES vaut `webmasters`, chaque rafraichissement d'un jeton emis avant
    l'elargissement logguait `Not all requested scopes were granted ... missing
    scopes https://www.googleapis.com/auth/webmasters`. Rien de casse, mais un
    log qui hurle « scope manquant » pile pendant la surveillance des logs
    post-deploiement, y compris une fois par article pour le cron d'attribution.
    """

    FICHIERS = ('proof_loop.py', 'views.py', 'autopilot.py')

    def test_aucune_construction_de_credentials_ne_passe_scopes(self):
        dossier = os.path.dirname(os.path.abspath(__file__))
        fautifs = []
        for nom in self.FICHIERS:
            chemin = os.path.join(dossier, nom)
            arbre = ast.parse(io.open(chemin, encoding='utf-8').read())
            for node in ast.walk(arbre):
                if not isinstance(node, ast.Call):
                    continue
                appele = node.func
                cible = getattr(appele, 'id', None) or getattr(appele, 'attr', None)
                if cible != 'Credentials':
                    continue
                if any(k.arg == 'scopes' for k in node.keywords):
                    fautifs.append('%s:%d' % (nom, node.lineno))
        self.assertEqual(fautifs, [], 'Credentials(scopes=...) reintroduit : %s' % fautifs)

    def test_le_flow_oauth_garde_ses_scopes(self):
        """L'inverse doit rester vrai : c'est le Flow qui demande le consentement,
        lui sans scopes ne demanderait plus rien."""
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'views.py')
        source = io.open(chemin, encoding='utf-8').read()
        self.assertEqual(source.count('scopes=GSC_SCOPES'), 2,
                         'les deux Flow.from_client_config doivent garder scopes=GSC_SCOPES')


class ProprieteCouvreTests(TestCase):
    """Google refuse un sitemap qui n'est pas DANS la propriete."""

    def test_domaine_couvre_host_et_sous_domaines(self):
        p = 'sc-domain:gridar.app'
        self.assertTrue(proof_loop.property_covers(p, 'https://gridar.app/sitemap.xml'))
        self.assertTrue(proof_loop.property_covers(p, 'https://www.gridar.app/sitemap.xml'))
        self.assertTrue(proof_loop.property_covers(p, 'https://blog.gridar.app/sitemap.xml'))
        self.assertFalse(proof_loop.property_covers(p, 'https://gridar.app.evil.com/s.xml'))
        self.assertFalse(proof_loop.property_covers(p, 'https://notgridar.app/sitemap.xml'))

    def test_prefixe_url_ne_couvre_que_son_prefixe(self):
        p = 'https://www.gridar.app/'
        self.assertTrue(proof_loop.property_covers(p, 'https://www.gridar.app/sitemap.xml'))
        self.assertFalse(proof_loop.property_covers(p, 'https://gridar.app/sitemap.xml'))
        # le cas mode hosted : blog sur un sous-domaine, propriete sur la racine
        self.assertFalse(proof_loop.property_covers(
            'https://restaurant.ca/', 'https://blog.restaurant.ca/sitemap.xml'))

    def test_prefixe_ne_matche_pas_un_domaine_voisin(self):
        """Sans le '/' final impose, 'https://gridar.app' matcherait
        'https://gridar.appareil.com/'."""
        self.assertFalse(proof_loop.property_covers(
            'https://gridar.app', 'https://gridar.appareil.com/sitemap.xml'))


class ClassificationErreurTests(TestCase):
    """La classification lit les champs STRUCTURES, jamais str(exc) : l'URI de
    la requete (donc le domaine du client) y figure."""

    def test_scope_insuffisant(self):
        self.assertEqual(proof_loop._classify_gsc_error(ERR_SCOPE()), 'readonly')

    def test_pas_proprietaire(self):
        self.assertEqual(proof_loop._classify_gsc_error(ERR_PAS_PROPRIETAIRE()), 'not_owner')

    def test_jeton_revoque(self):
        if _refresh_error_cls() is None:
            self.skipTest('google-auth absent de cet interpreteur')
        self.assertEqual(proof_loop._classify_gsc_error(erreur_refresh()), 'reauth')

    def test_un_domaine_contenant_scope_ne_declenche_pas_readonly(self):
        """LE faux positif de l'ancienne detection par sous-chaine : un client
        sur telescope.io prenait n'importe quel 403 pour un probleme de scope et
        se voyait ordonner de reconnecter Search Console, en boucle."""
        err = erreur_http(
            403, [{'message': 'Search Console API has not been used in project 42',
                   'reason': 'SERVICE_DISABLED'}],
            'https://searchconsole.googleapis.com/webmasters/v3/sites/'
            'https%3A%2F%2Ftelescope.io%2F/sitemaps/https%3A%2F%2Ftelescope.io%2Fsitemap.xml',
            reason='Search Console API has not been used in project 42 before or it is disabled.')
        self.assertEqual(proof_loop._classify_gsc_error(err), '')

    def test_erreur_quelconque_nest_pas_classee(self):
        self.assertEqual(proof_loop._classify_gsc_error(ERR_INTROUVABLE()), '')
        self.assertEqual(proof_loop._classify_gsc_error(None), '')


class SitemapParDefautTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sm1', password='x')

    def test_prend_le_domaine_public_avec_son_www(self):
        """Le www compte : gridar.app sert ses pages sur www, un sitemap soumis
        au host nu ne couvre pas la propriete ou vivent les URLs."""
        site = Site.objects.create(owner=self.user, name='G', domain='gridar.app',
                                   public_blog_domain='https://www.gridar.app')
        self.assertEqual(proof_loop.default_sitemap_url(site),
                         'https://www.gridar.app/sitemap.xml')

    def test_retombe_sur_le_domaine_du_site_et_force_https(self):
        site = Site.objects.create(owner=self.user, name='Q', domain='qrstudio.agency')
        self.assertEqual(proof_loop.default_sitemap_url(site),
                         'https://qrstudio.agency/sitemap.xml')

    def test_sans_domaine_rien_de_fabrique(self):
        site = Site.objects.create(owner=self.user, name='V', domain='')
        self.assertEqual(proof_loop.default_sitemap_url(site), '')


class SoumettreSitemapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sm2', password='x')
        self.site = Site.objects.create(owner=self.user, name='G', domain='gridar.app',
                                        public_blog_domain='https://www.gridar.app')
        self.site.gsc_refresh_token = 'fake-token'
        self.site.gsc_property_url = 'https://www.gridar.app/'
        self.site.save()

    def _appel(self, svc, sitemap_url='', propriete='https://www.gridar.app/'):
        with patch.object(proof_loop, '_build_gsc_service', return_value=svc), \
             patch.object(proof_loop, 'resolve_gsc_property', return_value=propriete):
            return proof_loop.submit_sitemap(self.site, sitemap_url)

    def test_succes_appelle_lapi_avec_la_propriete_et_le_sitemap(self):
        svc = _service()
        res = self._appel(svc)
        self.assertTrue(res['ok'])
        self.assertFalse(res['needs_reconnect'])
        svc.sitemaps.return_value.submit.assert_called_once_with(
            siteUrl='https://www.gridar.app/',
            feedpath='https://www.gridar.app/sitemap.xml')

    def test_sitemap_explicite_gagne_sur_le_defaut(self):
        svc = _service()
        res = self._appel(svc, 'https://www.gridar.app/sitemap-blog.xml')
        self.assertTrue(res['ok'])
        self.assertEqual(res['sitemap'], 'https://www.gridar.app/sitemap-blog.xml')

    def test_propriete_qui_ne_couvre_pas_le_sitemap_bascule_sur_la_bonne(self):
        """LE cas gridar.app : resolve_gsc_property prefere le host NU (il essaie
        ce candidat avant le www), alors que les pages et le sitemap vivent sur
        www. Sans bascule, Google refuse et personne ne relie l'erreur au vrai
        probleme."""
        svc = _service(entries=['https://gridar.app/', 'https://www.gridar.app/'])
        res = self._appel(svc, propriete='https://gridar.app/')
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['property'], 'https://www.gridar.app/')
        svc.sitemaps.return_value.submit.assert_called_once_with(
            siteUrl='https://www.gridar.app/',
            feedpath='https://www.gridar.app/sitemap.xml')

    def test_propriete_domaine_choisie_en_dernier_recours(self):
        """Une propriete sc-domain couvre tout ; elle ne doit pas voler la place
        d'un prefixe d'URL plus specifique, mais elle sauve le cas sous-domaine."""
        svc = _service(entries=['sc-domain:restaurant.ca'])
        site = Site.objects.create(owner=self.user, name='R', domain='restaurant.ca',
                                   public_blog_domain='https://blog.restaurant.ca')
        site.gsc_refresh_token = 'fake-token'
        site.save()
        with patch.object(proof_loop, '_build_gsc_service', return_value=svc), \
             patch.object(proof_loop, 'resolve_gsc_property',
                          return_value='https://restaurant.ca/'):
            res = proof_loop.submit_sitemap(site)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['property'], 'sc-domain:restaurant.ca')

    def test_aucune_propriete_ne_couvre_le_sitemap(self):
        svc = _service(entries=['https://autre-site.com/'])
        res = self._appel(svc, propriete='https://gridar.app/')
        self.assertFalse(res['ok'])
        self.assertEqual(res['code'], 'sitemap_hors_propriete')
        self.assertFalse(res['needs_reconnect'])
        svc.sitemaps.return_value.submit.assert_not_called()

    def test_jeton_lecture_seule_demande_une_reconnexion(self):
        """Le cas qui va vraiment arriver : les sites deja connectes portent un
        jeton emis sous l'ancien scope. Le message doit dire quoi faire."""
        svc = _service()
        svc.sitemaps.return_value.submit.return_value.execute.side_effect = ERR_SCOPE()
        res = self._appel(svc)
        self.assertFalse(res['ok'])
        self.assertTrue(res['needs_reconnect'])
        self.assertEqual(res['code'], 'gsc_scope_readonly')
        self.assertIn('LECTURE SEULE', res['error'])

    def test_jeton_revoque_demande_une_reconnexion(self):
        """Le refresh a lieu au premier appel, donc un jeton mort ressort ICI,
        en RefreshError et non en HttpError. C'est LE cas ou reconnecter est la
        reparation, et il tombait dans la branche generique."""
        if _refresh_error_cls() is None:
            self.skipTest('google-auth absent de cet interpreteur')
        svc = _service()
        svc.sitemaps.return_value.submit.return_value.execute.side_effect = erreur_refresh()
        res = self._appel(svc)
        self.assertFalse(res['ok'])
        self.assertTrue(res['needs_reconnect'])
        self.assertEqual(res['code'], 'gsc_reauth_required')

    def test_jeton_revoque_pendant_la_resolution_ne_dit_pas_propriete_absente(self):
        """Variante deja vue en prod : sites().list() echoue sur le jeton mort,
        et on annoncait « aucune propriete verifiee » a un client dont le jeton
        etait simplement expire. Il va chercher au mauvais endroit."""
        if _refresh_error_cls() is None:
            self.skipTest('google-auth absent de cet interpreteur')
        svc = _service()
        svc.sites.return_value.list.return_value.execute.side_effect = erreur_refresh()
        res = self._appel(svc, propriete='')
        self.assertFalse(res['ok'])
        self.assertEqual(res['code'], 'gsc_reauth_required')
        self.assertIn('revoque', res['error'])

    def test_403_non_proprietaire_nest_pas_un_probleme_de_scope(self):
        """Reconnecter le meme compte ne repare pas ce 403 la : ne pas envoyer
        Darius sur une fausse piste."""
        svc = _service()
        svc.sitemaps.return_value.submit.return_value.execute.side_effect = ERR_PAS_PROPRIETAIRE()
        res = self._appel(svc)
        self.assertFalse(res['ok'])
        self.assertFalse(res['needs_reconnect'])
        self.assertEqual(res['code'], 'gsc_not_owner')

    def test_autre_erreur_remonte_telle_quelle(self):
        svc = _service()
        svc.sitemaps.return_value.submit.return_value.execute.side_effect = ERR_INTROUVABLE()
        res = self._appel(svc)
        self.assertFalse(res['ok'])
        self.assertFalse(res['needs_reconnect'])
        self.assertIsNone(res.get('code'))

    def test_gsc_non_connectee(self):
        with patch.object(proof_loop, '_build_gsc_service', return_value=None):
            res = proof_loop.submit_sitemap(self.site)
        self.assertFalse(res['ok'])
        self.assertIn('non connectee', res['error'])

    def test_sans_propriete_resolue_ni_trouvee_on_ne_soumet_rien(self):
        svc = _service(entries=[])
        res = self._appel(svc, propriete='')
        self.assertFalse(res['ok'])
        svc.sitemaps.return_value.submit.assert_not_called()

    def test_sans_domaine_on_ne_construit_meme_pas_le_client(self):
        site = Site.objects.create(owner=self.user, name='V', domain='')
        with patch.object(proof_loop, '_build_gsc_service') as build:
            res = proof_loop.submit_sitemap(site)
        self.assertFalse(res['ok'])
        build.assert_not_called()


class EndpointSitemapSubmitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='sm3', password='x')
        self.site = Site.objects.create(owner=self.user, name='G', domain='gridar.app',
                                        public_blog_domain='https://www.gridar.app')
        self.factory = APIRequestFactory()

    def _post(self, data=None):
        req = self.factory.post(f'/api/v1/sites/{self.site.id}/sitemap/submit/',
                                data if data is not None else {}, format='json')
        force_authenticate(req, user=self.user)
        return V1SitemapSubmitView.as_view()(req, site_id=self.site.id)

    def test_succes_200(self):
        with patch.object(proof_loop, 'submit_sitemap',
                          return_value={'ok': True, 'sitemap': 'x', 'needs_reconnect': False}):
            resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['site_id'], self.site.id)

    def test_jeton_lecture_seule_rend_409(self):
        """409 et pas 400 : la requete est valable, c'est l'etat de la connexion
        qui bloque, et l'appelant a un geste precis a faire."""
        with patch.object(proof_loop, 'submit_sitemap',
                          return_value={'ok': False, 'needs_reconnect': True,
                                        'code': 'gsc_scope_readonly',
                                        'error': 'LECTURE SEULE'}):
            resp = self._post()
        self.assertEqual(resp.status_code, 409)

    def test_jeton_mort_rend_401_avec_le_code_deja_gere_par_le_frontend(self):
        with patch.object(proof_loop, 'submit_sitemap',
                          return_value={'ok': False, 'needs_reconnect': True,
                                        'code': 'gsc_reauth_required', 'error': 'expire'}):
            resp = self._post()
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.data['code'], 'gsc_reauth_required')

    def test_autre_echec_rend_400(self):
        with patch.object(proof_loop, 'submit_sitemap',
                          return_value={'ok': False, 'needs_reconnect': False,
                                        'error': 'boom'}):
            resp = self._post()
        self.assertEqual(resp.status_code, 400)

    def test_le_sitemap_fourni_est_transmis(self):
        with patch.object(proof_loop, 'submit_sitemap',
                          return_value={'ok': True, 'needs_reconnect': False}) as f:
            self._post({'sitemap_url': 'https://www.gridar.app/sitemap-blog.xml'})
        self.assertEqual(f.call_args[0][1], 'https://www.gridar.app/sitemap-blog.xml')

    def test_sitemap_url_non_chaine_rend_400_sans_appeler_google(self):
        with patch.object(proof_loop, 'submit_sitemap') as f:
            resp = self._post({'sitemap_url': {'evil': 1}})
        self.assertEqual(resp.status_code, 400)
        f.assert_not_called()

    def test_site_dun_autre_utilisateur_inaccessible(self):
        autre = User.objects.create_user(username='sm4', password='x')
        req = self.factory.post(f'/api/v1/sites/{self.site.id}/sitemap/submit/', {}, format='json')
        force_authenticate(req, user=autre)
        resp = V1SitemapSubmitView.as_view()(req, site_id=self.site.id)
        self.assertIn(resp.status_code, (403, 404))


class DocClientTests(TestCase):
    """La page publique gridar.app/docs/gsc promettait a des clients payants
    « uniquement webmasters.readonly ... on ne peut pas soumettre de sitemaps ».
    L'elargissement rend cette phrase fausse : elle doit tomber avec le code."""

    def _doc(self):
        chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', '..', 'marketing', 'docs', 'gsc.md')
        chemin = os.path.normpath(chemin)
        if not os.path.exists(chemin):
            self.skipTest('doc marketing absente de cet arbre')
        return io.open(chemin, encoding='utf-8').read()

    def test_la_promesse_de_lecture_seule_a_disparu(self):
        doc = self._doc()
        self.assertNotIn('uniquement `webmasters.readonly`', doc)
        self.assertNotIn('- Soumettre / supprimer des sitemaps', doc)

    def test_la_doc_annonce_le_scope_reel_et_la_reconnexion(self):
        doc = self._doc()
        self.assertIn('`webmasters`', doc)
        self.assertIn('lecture seule', doc)  # le cas des connexions anterieures
