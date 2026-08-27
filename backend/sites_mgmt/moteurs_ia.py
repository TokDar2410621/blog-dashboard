"""Interrogation des moteurs d'IA dont on mesure les reponses.

Pourquoi ce module existe
-------------------------
Trois outils publics posent la meme question : "quand quelqu'un demande X a
une IA, est-ce que ce site est cite ?". Ils appelaient chacun Gemini
directement, avec leur propre gestion d'erreur, et tous partageaient le meme
defaut : une panne du moteur se lisait comme une absence de mention.

Ici, un moteur qui ne repond pas le DIT. La difference n'est pas cosmetique :
"l'IA ne parle pas de ton site" et "on n'a pas pu demander a l'IA" sont deux
resultats opposes, et le second affiche a la place du premier est un mensonge
sur le site de quelqu'un.

Le contrat
----------
`interroger(moteur, question)` rend toujours :

    {
        'moteur': str,
        'texte': str | None,     # la reponse, ou None
        'disponible': bool,
        'raison': str | None,    # pourquoi c'est indisponible
    }

Les deux pieges du raisonnement
-------------------------------
Les modeles recents consomment des jetons de reflexion QUI COMPTENT dans le
budget de sortie. Verifie en prod le 2026-08-27 :

    gpt-5-mini  budget 200  raisonnement=200  texte=0 car   finish=length
    gpt-5-mini  budget 800  raisonnement=800  texte=0 car   finish=length
    gpt-5-mini  budget 800  effort=minimal  raisonnement=0  texte=1874 car

Augmenter le budget n'aide pas, le modele reflechit simplement plus
longtemps. Il faut couper la reflexion : `reasoning_effort: minimal` chez
OpenAI, `thinkingBudget: 0` chez Gemini. Sans ca, on paye des jetons pour
recevoir du vide, et le vide se compte comme une non-mention.
"""
import logging
import os

import requests as http_requests

logger = logging.getLogger(__name__)

# Ordre d'affichage. Un moteur absent de la configuration est simplement
# saute, il n'apparait pas comme "0 mention".
MOTEURS_CONNUS = ('gemini', 'openai')

LIBELLES = {
    'gemini': "l'IA de Google (Gemini)",
    'openai': 'ChatGPT (OpenAI)',
}

_GEMINI_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    'gemini-2.5-flash:generateContent'
)
_OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
_MODELE_OPENAI = 'gpt-5-mini'


def _indisponible(moteur: str, raison: str) -> dict:
    return {'moteur': moteur, 'texte': None, 'disponible': False, 'raison': raison}


def _reponse(moteur: str, texte: str) -> dict:
    return {'moteur': moteur, 'texte': texte, 'disponible': True, 'raison': None}


def moteurs_configures() -> list[str]:
    """Les moteurs dont la cle est presente. Un moteur sans cle n'est pas une
    panne, il n'est simplement pas interroge."""
    presents = []
    if os.environ.get('GEMINI_API_KEY'):
        presents.append('gemini')
    if os.environ.get('OPENAI_API_KEY'):
        presents.append('openai')
    return presents


def _interroger_gemini(question: str, timeout: int) -> dict:
    cle = os.environ.get('GEMINI_API_KEY')
    if not cle:
        return _indisponible('gemini', 'Cle absente.')
    try:
        r = http_requests.post(
            _GEMINI_URL,
            # La cle passe par un en-tete : dans une URL, elle finit dans le
            # message des exceptions HTTP, donc dans les logs.
            headers={'x-goog-api-key': cle},
            json={
                'contents': [{'parts': [{'text': question}]}],
                'generationConfig': {
                    'maxOutputTokens': 700,
                    'thinkingConfig': {'thinkingBudget': 0},
                },
            },
            timeout=timeout,
        )
    except Exception as e:
        return _indisponible('gemini', f'Appel impossible ({type(e).__name__}).')

    if r.status_code == 429:
        return _indisponible('gemini', 'Quota epuise.')
    if r.status_code != 200:
        return _indisponible('gemini', f'Reponse HTTP {r.status_code}.')
    try:
        parts = (r.json().get('candidates') or [{}])[0] \
            .get('content', {}).get('parts') or []
        texte = ''.join(p.get('text', '') for p in parts).strip()
    except Exception:
        return _indisponible('gemini', 'Reponse illisible.')
    if not texte:
        # Reponse vide malgre un 200 : typiquement la reflexion a mange le
        # budget. Ce n'est pas une absence de mention.
        return _indisponible('gemini', 'Reponse vide.')
    return _reponse('gemini', texte)


def _interroger_openai(question: str, timeout: int) -> dict:
    cle = os.environ.get('OPENAI_API_KEY')
    if not cle:
        return _indisponible('openai', 'Cle absente.')
    try:
        r = http_requests.post(
            _OPENAI_URL,
            headers={'Authorization': f'Bearer {cle}',
                     'Content-Type': 'application/json'},
            json={
                'model': _MODELE_OPENAI,
                'messages': [{'role': 'user', 'content': question}],
                'max_completion_tokens': 800,
                # Sans ca, le modele consomme la totalite du budget en
                # reflexion et rend une chaine vide (mesure en prod).
                'reasoning_effort': 'minimal',
            },
            timeout=timeout,
        )
    except Exception as e:
        return _indisponible('openai', f'Appel impossible ({type(e).__name__}).')

    if r.status_code == 429:
        return _indisponible('openai', 'Quota epuise.')
    if r.status_code != 200:
        return _indisponible('openai', f'Reponse HTTP {r.status_code}.')
    try:
        choix = (r.json().get('choices') or [{}])[0]
        texte = (choix.get('message', {}).get('content') or '').strip()
        fin = choix.get('finish_reason')
    except Exception:
        return _indisponible('openai', 'Reponse illisible.')

    if fin == 'length' and not texte:
        return _indisponible('openai', 'Budget de jetons epuise avant la reponse.')
    if not texte:
        return _indisponible('openai', 'Reponse vide.')
    return _reponse('openai', texte)


def interroger(moteur: str, question: str, timeout: int = 25) -> dict:
    """Pose une question a un moteur. Ne leve jamais.

    Un moteur inconnu est declare indisponible plutot que traverse en
    silence : l'ancien `_check_ai_mention` rendait `mentioned: False` pour
    tout moteur autre que 'gemini', sans le moindre appel reseau ni log, ce
    qui aurait fait passer un moteur non implemente pour un moteur qui ne
    cite jamais personne.
    """
    if moteur == 'gemini':
        return _interroger_gemini(question, timeout)
    if moteur == 'openai':
        return _interroger_openai(question, timeout)
    return _indisponible(moteur, 'Moteur inconnu.')
