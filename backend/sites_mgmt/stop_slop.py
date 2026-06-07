"""Anti-slop guardrails injected into the article-generation prompt.

Adapted from the stop-slop skill (Hardik Pandya, MIT) for the Gridar use
case: FR-CA + EN versions tailored to SEO blog content. Rules complement
(do not contradict) the existing TON & STYLE block of the prompt.

Why this exists:
  Claude tends to fall back into AI-writing tells when generating long-form
  content - throat-clearing openers, binary contrasts, vague declaratives,
  em-dashes, narrator-from-a-distance voice. These patterns kill the
  authentic founder voice the prompt asks for, and they are the #1 reason
  readers (and Google) mark content as low-effort AI slop.

Usage:
  from .stop_slop import get_stop_slop_block
  block = get_stop_slop_block('fr')  # or 'en' / 'es'
  prompt = f"... {block} ..."
"""
from __future__ import annotations


STOP_SLOP_FR = """
**ANTI-AI-SLOP (regles strictes, lis avant d'ecrire) :**

Ces formules sonnent IA et tuent la confiance du lecteur. Ne les utilise jamais.

1. Phrases d'ouverture interdites (juste delete et va droit au point) :
   - "Soyons clairs", "Voici pourquoi", "Voyons ca", "En realite", "A vrai dire",
     "C'est simple :", "Au fond", "Au final", "Pour etre honnete", "Bonne nouvelle :",
     "Mauvaise nouvelle :", "Detail interessant :", "Petit rappel :", "Pour situer :"
   - Toute construction "Voici ce que / Voici comment / Voici pourquoi" est du
     raclage de gorge. Coupe et dis le truc directement.

2. Tirets longs interdits :
   - Aucun em-dash (-) ni en-dash (-) dans le texte. Utilise un trait d'union
     ASCII (-), des virgules, ou deux points. Si une phrase a besoin d'un em-dash,
     c'est qu'elle est mal construite, reecris-la.

3. Adverbes a couper en -ment et leurs versions courtes :
   - "vraiment", "simplement", "honnetement", "litteralement", "veritablement",
     "fondamentalement", "naturellement", "evidemment", "clairement",
     "manifestement", "incroyablement", "completement", "totalement",
     "essentiellement", "principalement"
   - Si la phrase tient sans l'adverbe, supprime-le. Si elle ne tient pas, l'adverbe
     cache un mot precis manquant - trouve-le.

4. Jargon corporate banni :
   - "naviguer (les defis)" -> "gerer", "regler"
   - "se pencher sur" -> "analyser", "examiner"
   - "approfondir / creuser le sujet" -> "expliquer", "detailler"
   - "se reinventer" -> dis ce que la personne fait concretement
   - "a la croisee des chemins" -> nomme la decision precise
   - "game-changer" -> dis pourquoi c'est important
   - "passer au niveau superieur" -> nomme le niveau

5. Contrastes binaires (faux drame) interdits :
   - "Ce n'est pas X. C'est Y." / "Ce n'est pas X, c'est Y."
   - "X n'est pas le probleme. Y l'est."
   - "La vraie question n'est pas X. C'est Y."
   - "On croit que X. En realite, c'est Y."
   - Solution : ecris Y directement. Le lecteur n'a pas besoin du contraste pour
     comprendre.

6. Declarations vagues interdites :
   - "Les enjeux sont enormes", "Les implications sont significatives",
     "Ca change tout", "C'est un tournant", "Les consequences sont reelles".
   - Si tu sens venir une phrase comme ca, remplace-la par l'exemple precis qui
     prouve l'enjeu.

7. Fragmentation dramatique interdite :
   - Phrases d'un mot pour faire "effet". Trois fragments consecutifs pour faire
     "rythme". Une majuscule. Un point. Voila. <- exactement le pattern a eviter.
   - Ecris des phrases completes. La force vient du contenu, pas du staccato.

8. Fausses agences (interdites) :
   - "La decision emerge", "La culture evolue", "Le marche recompense",
     "Les donnees nous disent", "La situation devient..."
   - Les choses inertes ne font pas d'actions humaines. Nomme la personne :
     "L'equipe a decide", "Les fondateurs ont change leur comportement",
     "Les acheteurs payent pour X".

9. Voix passive interdite :
   - "Il a ete decide que...", "Une erreur a ete commise...", "Il est convenu que..."
   - Trouve qui a fait l'action et mets-le en sujet : "Le client a decide",
     "Marie a fait l'erreur", "L'equipe a convenu".

10. Meta-commentaire interdit :
    - "Dans la suite, on va voir...", "Comme on va le voir...", "Petit rappel...",
      "Maintenant, parlons de...", "Avant de continuer..."
    - L'article doit avancer, pas annoncer sa propre structure. Coupe ces phrases,
      enchaine directement.

11. Listes a trois elements (eviter par defaut) :
    - L'IA pond des listes a trois automatiquement. Si tu peux le dire en deux
      points, fais-le. Si tu peux le dire en un, fais-le. Trois c'est seulement
      quand il y a vraiment trois choses distinctes.

12. Lazy extremes interdits :
    - "tout le monde", "personne", "toujours", "jamais", "chaque", "aucun"
    - Sauf si c'est techniquement vrai (lois physiques, faits). Remplace par
      "la plupart", "rarement", un chiffre, ou un exemple.

**Test final avant de soumettre l'article :**
- Aucun em-dash dans tout le texte ? OK.
- Aucun adverbe en -ment qui ne porte pas de sens ? OK.
- Aucune phrase qui commence par "Voici ce que / Voila pourquoi / Soyons clairs" ? OK.
- Chaque paragraphe avance le sujet au lieu de l'annoncer ? OK.
- Si je lis a voix haute, ca sonne comme un humain qui sait de quoi il parle ? OK.
"""


STOP_SLOP_EN = """
**ANTI-AI-SLOP rules (read before writing):**

These patterns scream AI and kill reader trust. Never use them.

1. Banned throat-clearing openers (delete and state the point):
   - "Here's the thing:", "Here's what / Here's why / Here's how", "Look,",
     "The truth is,", "The uncomfortable truth is", "Let's be clear",
     "Let me be honest", "It turns out", "The real X is",
     "I'll say it again:", "Let me walk you through".

2. No em-dashes or en-dashes anywhere. Use ASCII hyphens (-), commas, or
   colons. A sentence that needs an em-dash is a sentence to rewrite.

3. Banned adverbs (cut all -ly fillers):
   - "really", "just", "literally", "genuinely", "honestly", "simply",
     "actually", "deeply", "truly", "fundamentally", "inherently",
     "inevitably", "interestingly", "importantly", "crucially".
   - If the sentence still says what it means without the adverb, drop it. If
     not, the adverb is hiding a precise word that's missing - find it.

4. Banned corporate jargon:
   - "navigate (challenges)" -> "handle", "address"
   - "unpack" -> "explain", "examine"
   - "lean into" -> "accept", "do more of"
   - "game-changer" -> state why it matters
   - "moving forward" -> "next", "from now"

5. Banned binary contrasts (manufactured drama):
   - "Not X. Y." / "It's not X, it's Y."
   - "X isn't the problem. Y is."
   - "The question isn't X. It's Y."
   - "What we think is X. What's actually true is Y."
   - Just write Y. The reader doesn't need the setup.

6. Banned vague declaratives:
   - "The stakes are high", "The implications are significant",
     "This changes everything", "The consequences are real".
   - If you feel one coming, replace with the concrete example that proves it.

7. Banned dramatic fragmentation:
   - One-word sentences for effect. Three fragments in a row. Punchy. Period.
     Done. <- this exact pattern.
   - Write complete sentences. Force comes from content, not staccato.

8. Banned false agency (no inanimate verbs):
   - "The decision emerges", "The culture shifts", "The market rewards",
     "The data tells us".
   - Name the human. "The team decided", "Buyers paid for X", "We read the
     data and concluded Y".

9. Banned passive voice:
   - "Mistakes were made", "The decision was reached", "It is believed that".
   - Find the actor, put them at the front: "Marie made the mistake", "The
     board decided", "Most users believe".

10. Banned meta-commentary:
    - "In what follows...", "We'll see that...", "As we'll discuss...",
      "Before moving on...", "A quick reminder...".
    - Move the article forward instead of announcing its own structure.

11. Avoid default three-item lists:
    - Two items, or one, when you can. Three only when there genuinely are
      three distinct things.

12. Banned lazy extremes:
    - "everyone", "nobody", "always", "never", "every", "all".
    - Use "most", "rarely", a specific number, or an example, unless the
      extreme is literally true.

**Final check before submitting the article:**
- Zero em-dashes in the text? OK.
- No empty adverbs left? OK.
- No sentence starts with "Here's what / Here's why / Look,"? OK.
- Every paragraph advances the topic instead of announcing it? OK.
- Read aloud: sounds like a human who knows the subject? OK.
"""


# Spanish version - shorter, focused on the same banned-patterns checklist.
# Localized terms; not a 1:1 translation of the FR block.
STOP_SLOP_ES = """
**ANTI-SLOP-DE-IA (reglas estrictas):**

Estas formulas suenan a IA y matan la confianza del lector.

1. Aperturas prohibidas: "Vamos a ver", "Aqui esta lo que", "La verdad es que",
   "Para ser honesto", "Veamos esto". Borra y dile la idea directamente.
2. Sin guiones largos: solo guion ASCII (-), comas o dos puntos.
3. Sin adverbios vacios en -mente: "realmente", "simplemente", "honestamente",
   "literalmente", "verdaderamente", "fundamentalmente", "claramente".
4. Sin contrastes binarios falsos: "No es X. Es Y." / "El problema no es X, es Y."
   Escribe Y directamente.
5. Sin declaraciones vagas: "Las consecuencias son enormes", "Lo cambia todo".
   Reemplaza por el ejemplo concreto.
6. Sin voz pasiva: nombra al actor.
7. Sin agencia falsa: las cosas inertes no actuan. "El equipo decidio", no
   "La decision surge".
8. Sin metacomentario: el articulo avanza, no se anuncia.
9. Evita listas de tres por defecto.
10. Evita extremos perezosos ("todos", "nadie", "siempre", "nunca").
"""


_BLOCKS = {
    'fr': STOP_SLOP_FR,
    'en': STOP_SLOP_EN,
    'es': STOP_SLOP_ES,
}


def get_stop_slop_block(language: str = 'fr') -> str:
    """Return the anti-slop rules block for the given language.

    Falls back to French if the language is unsupported (matches the
    primary FR-CA Quebec market of Gridar).
    """
    return _BLOCKS.get((language or 'fr').lower()[:2], STOP_SLOP_FR)
