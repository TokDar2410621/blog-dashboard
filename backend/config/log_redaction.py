"""Masquage des secrets avant ecriture dans les logs.

Pourquoi ce module existe
-------------------------
Le 2026-08-27, la cle `GEMINI_API_KEY` s'est retrouvee EN CLAIR dans les logs
Railway. La chaine, en trois maillons dont aucun n'est suspect isolement :

1. La cle etait interpolee dans l'URL (`...generateContent?key=AIza...`).
2. `raise_for_status()` leve une `HTTPError` dont le message contient l'URL
   COMPLETE, parametres inclus.
3. Un `except Exception: logger.exception(...)` en amont ecrivait ce message
   dans les logs.

Chaque maillon corrige separement laisse le suivant intact. Les cles sont
donc passees en en-tetes (le correctif a la source), et ce module est la
ceinture : il protege le code FUTUR, celui qu'on n'a pas encore ecrit et qui
loggera une exception sans se demander ce qu'elle contient.

Deux passes complementaires
---------------------------
1. **Par valeur** : les valeurs reelles des variables d'environnement qui
   ressemblent a un secret sont remplacees, ou qu'elles apparaissent. C'est
   la passe qui attrape un secret sans prefixe reconnaissable, par exemple
   dans un `repr()` de dict d'en-tetes.
2. **Par motif** : `key=`, `token=`, `Bearer ...` sont masques meme si la
   valeur n'est pas connue de ce processus. C'est la passe qui attrape le
   secret d'un tiers, ou une variable ajoutee apres le demarrage.

Ce module est charge pendant la lecture des settings, donc AVANT que les
applications Django soient pretes : il ne doit importer que la bibliotheque
standard.
"""
import logging
import os
import re

MASQUE = '***masque***'

# En dessous de cette longueur, une valeur d'environnement est trop banale
# pour etre remplacee sans risque : masquer un "1" ou un "True" rendrait les
# logs illisibles et n'ajouterait aucune securite.
_LONGUEUR_MINIMALE = 12

_NOMS_SENSIBLES = re.compile(
    r'(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN|SENTRY)', re.IGNORECASE)

# Valeurs qu'il ne faut PAS masquer meme si leur nom matche : ce sont des
# identifiants publics ou des URL de service, et les remplacer casserait le
# diagnostic sans rien proteger.
_NOMS_EXCLUS = re.compile(
    r'^(STRIPE_PUBLISHABLE_KEY|STRIPE_PRICE_|.*_PUBLIC_.*|.*_URL)$',
    re.IGNORECASE)

# Motifs generiques : un secret annonce par son nom dans une chaine.
# Le `["\']?` apres le nom couvre le repr() d'un dict, ou la cle est citee :
# `{'x-goog-api-key': 'AIza...'}`. Sans lui, la quote fermante separait le nom
# du deux-points et le motif ne matchait pas.
_MOTIF_PARAMETRE = re.compile(
    r'((?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|key|token|secret|password)'
    r'["\']?\s*[=:]\s*)(["\']?)([^\s&"\'<>,;)\]}]{8,})',
    re.IGNORECASE)
_MOTIF_PORTEUR = re.compile(r'(Bearer\s+)([A-Za-z0-9._\-]{8,})', re.IGNORECASE)


def _valeurs_a_masquer() -> list[str]:
    """Valeurs d'environnement qui ressemblent a un secret.

    Lues une fois au chargement : l'environnement d'un processus ne change
    pas en cours de route, et relire os.environ a chaque ligne de log serait
    un cout inutile sur le chemin le plus chaud du programme.
    """
    trouvees = set()
    for nom, valeur in os.environ.items():
        if not valeur or len(valeur) < _LONGUEUR_MINIMALE:
            continue
        if _NOMS_EXCLUS.match(nom):
            continue
        if _NOMS_SENSIBLES.search(nom):
            trouvees.add(valeur)
    # Les plus longues d'abord : si un secret est le prefixe d'un autre, le
    # remplacement partiel laisserait une trace du plus long.
    return sorted(trouvees, key=len, reverse=True)


_VALEURS = _valeurs_a_masquer()
_MOTIF_VALEURS = (
    re.compile('|'.join(re.escape(v) for v in _VALEURS)) if _VALEURS else None
)


def masquer(texte: str) -> str:
    """Rend `texte` sans secret lisible. Ne leve jamais.

    Un echec de masquage ne doit pas faire tomber le logging, mais il ne doit
    pas non plus laisser passer la ligne telle quelle : en cas d'imprevu on
    rend un texte neutre plutot que le contenu original.
    """
    try:
        sortie = str(texte)
        if _MOTIF_VALEURS is not None:
            sortie = _MOTIF_VALEURS.sub(MASQUE, sortie)
        sortie = _MOTIF_PARAMETRE.sub(lambda m: m.group(1) + m.group(2) + MASQUE, sortie)
        sortie = _MOTIF_PORTEUR.sub(lambda m: m.group(1) + MASQUE, sortie)
        return sortie
    except Exception:
        return '[ligne de log non masquable, contenu supprime par securite]'


class FormateurMasque(logging.Formatter):
    """Formateur qui masque les secrets de la ligne finale.

    Le masquage se fait APRES le formatage complet, donc il couvre le
    message, ses arguments ET le traceback rendu depuis `exc_info`. C'est
    justement le traceback qui portait la cle Gemini : un filtre travaillant
    sur `record.msg` seul serait passe a cote.
    """

    def format(self, record: logging.LogRecord) -> str:
        return masquer(super().format(record))
