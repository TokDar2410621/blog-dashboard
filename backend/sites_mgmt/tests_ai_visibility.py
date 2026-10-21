"""Tests : la visibilite IA du tableau de bord ne sert plus de chiffres inventes.

Contexte : la V1 de V1AiVisibilityRunView n'interrogeait aucun moteur IA. Elle
fabriquait des reponses ("[Gemini mock] ...") au hasard et les stockait comme
des mesures ; le score, les mentions et le detail par moteur les agregeaient.
Constate le 2026-10-21 pendant la mise a jour des docs publiques.

Le lancement repond maintenant 501 sans rien ecrire, et les lignes simulees
deja en base sont exclues du resume et de la liste des prompts.
Run: python manage.py test sites_mgmt.tests_ai_visibility
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from .api_v1 import (
    V1AiVisibilityPromptsView,
    V1AiVisibilityRunView,
    V1AiVisibilitySummaryView,
)
from .models import AiVisibilityPrompt, AiVisibilityResult, Site

User = get_user_model()


class VisibiliteIASansSimulationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='aiv', password='x', is_staff=True)
        self.site = Site.objects.create(owner=self.user, name='G', domain='gridar.app')
        self.prompt = AiVisibilityPrompt.objects.create(
            site=self.site, prompt='meilleur outil SEO quebec', language='fr')
        self.factory = APIRequestFactory()

    def _simulee(self, engine_label, engine, cited=True):
        return AiVisibilityResult.objects.create(
            prompt=self.prompt, engine=engine, is_cited=cited,
            response_excerpt=f'[{engine_label} mock] Pour repondre a "x", gridar.app ...',
            citation_url='https://gridar.app/blog' if cited else None,
            citation_rank=2 if cited else None,
        )

    def _get(self, view, path):
        req = self.factory.get(path)
        force_authenticate(req, user=self.user)
        return view.as_view()(req, site_id=self.site.id)

    def test_lancer_repond_501_et_ne_cree_aucune_ligne(self):
        req = self.factory.post(f'/api/v1/sites/{self.site.id}/ai-visibility/run/', {})
        force_authenticate(req, user=self.user)
        res = V1AiVisibilityRunView.as_view()(req, site_id=self.site.id)
        self.assertEqual(res.status_code, 501)
        self.assertEqual(res.data['code'], 'ai_visibility_unavailable')
        self.assertFalse(res.data['available'])
        self.assertEqual(AiVisibilityResult.objects.count(), 0)

    def test_resume_ignore_les_lignes_simulees(self):
        self._simulee('ChatGPT', 'chatgpt')
        self._simulee('Perplexity', 'perplexity')
        self._simulee('Gemini', 'gemini', cited=False)
        res = self._get(V1AiVisibilitySummaryView,
                        f'/api/v1/sites/{self.site.id}/ai-visibility/summary/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['score'], 0.0)
        self.assertEqual(res.data['total_checks'], 0)
        self.assertEqual(res.data['total_mentions'], 0)
        self.assertEqual(res.data['cited_pages_count'], 0)
        self.assertFalse(res.data['available'])
        self.assertTrue(res.data['note'])

    def test_resume_compte_une_vraie_mesure(self):
        """Une reponse non simulee reste comptee : le filtre ne vise que la V1."""
        self._simulee('ChatGPT', 'chatgpt')
        AiVisibilityResult.objects.create(
            prompt=self.prompt, engine='gemini', is_cited=True,
            response_excerpt='Gridar (gridar.app) automatise le SEO des PME.',
            citation_url='https://gridar.app/', citation_rank=1,
        )
        res = self._get(V1AiVisibilitySummaryView,
                        f'/api/v1/sites/{self.site.id}/ai-visibility/summary/')
        self.assertEqual(res.data['total_checks'], 1)
        self.assertEqual(res.data['total_mentions'], 1)

    def test_liste_des_prompts_ignore_les_lignes_simulees(self):
        self._simulee('Claude', 'claude')
        res = self._get(V1AiVisibilityPromptsView,
                        f'/api/v1/sites/{self.site.id}/ai-visibility/prompts/')
        self.assertEqual(res.status_code, 200)
        ligne = res.data['results'][0]
        self.assertEqual(ligne['total_checks'], 0)
        self.assertEqual(ligne['citation_count'], 0)
        self.assertEqual(ligne['engines_mentioning'], [])
        self.assertIsNone(ligne['last_checked_at'])
