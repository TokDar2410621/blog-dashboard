"""Budget guard on the paid APIs: cost estimate, verdict, ledger line.

Porte depuis claude-seo v2.2.4 `scripts/dataforseo_costs.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream prices 45 DataForSEO endpoints and keeps the running total in a JSON
file guarded by an `fcntl` lock. That is correct for a single-threaded CLI and
wrong here: Railway runs several instances against one Postgres, and a file
lock spans neither. So the guardrail logic is kept and the persistence is
dropped; what replaces it is the `BudgetStore` protocol, which the caller
implements over a transactional counter. The cost tables are Gridar's own two
providers and neither bills per call the way DataForSEO does, so Serper is
priced in credits and Anthropic in input and output tokens. Every verdict is
written in French because it reaches a Quebec operator, and every rate carries
the date it was verified since these move without warning.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

__all__ = [
    'BudgetError',
    'BudgetStore',
    'TARIFFS_CHECKED_ON',
    'TARIFF_SOURCES',
    'BUDGET_TIMEZONE',
    'SERPER_PLANS',
    'SERPER_OPERATIONS',
    'ANTHROPIC_MODELS',
    'WARN_AT_RATIO',
    'budget_day_key',
    'estimate_cost',
    'check_budget',
    'format_ledger_entry',
]


class BudgetError(ValueError):
    """Raised when a caller asks to price something this module cannot price."""


# --------------------------------------------------------------------------
# Tariffs
# --------------------------------------------------------------------------

# Rates move. Anything read below was verified on this date against the two
# sources; past a couple of months, re-verify before trusting an estimate.
TARIFFS_CHECKED_ON = '2026-08-14'

TARIFF_SOURCES = {
    'serper': 'https://serper.dev/ (page Tarifs)',
    'anthropic': 'https://platform.claude.com/docs/en/about-claude/models/overview',
}

# Serper sells credits up front, so the dollar value of one call depends on the
# plan the account is on. Default is the cheapest plan, which has the highest
# unit price: a guard that under-prices is worse than useless.
SERPER_PLANS = {
    'starter': 0.001,      # 50 $ / 50 000 credits
    'standard': 0.00075,   # 375 $ / 500 000 credits
    'scale': 0.0005,       # 1 250 $ / 2 500 000 credits
    'ultimate': 0.0003,    # 3 750 $ / 12 500 000 credits
}
DEFAULT_SERPER_PLAN = 'starter'

# Serper charges the same for every endpoint; the multiplier is depth, not kind.
SERPER_SHALLOW_MAX_RESULTS = 10
SERPER_DEEP_CREDITS = 2
SERPER_MAX_RESULTS = 100

SERPER_OPERATIONS = {
    'search': {'label': 'recherche web', 'credits': 1},
    'images': {'label': "recherche d'images", 'credits': 1},
    'news': {'label': 'actualités', 'credits': 1},
    'places': {'label': 'fiches locales', 'credits': 1},
    'maps': {'label': 'Google Maps', 'credits': 1},
    'videos': {'label': 'vidéos', 'credits': 1},
    'shopping': {'label': 'achats', 'credits': 1},
    'scholar': {'label': 'Google Scholar', 'credits': 1},
    'patents': {'label': 'brevets', 'credits': 1},
    'autocomplete': {'label': 'suggestions de recherche', 'credits': 1},
}

# Dollars per million tokens, public list prices. `intro` is a promotional
# window that reverts to the standard rate on its own, which is exactly the
# kind of thing a hardcoded number gets wrong three weeks later.
ANTHROPIC_MODELS = {
    'claude-opus-5': {'input': 5.00, 'output': 25.00},
    'claude-opus-4-8': {'input': 5.00, 'output': 25.00},
    'claude-sonnet-5': {
        'input': 3.00, 'output': 15.00,
        'intro': {'input': 2.00, 'output': 10.00, 'until': '2026-08-31'},
    },
    'claude-sonnet-4-6': {'input': 3.00, 'output': 15.00},
    'claude-haiku-4-5': {'input': 1.00, 'output': 5.00},
    'claude-fable-5': {'input': 10.00, 'output': 50.00},
}
DEFAULT_ANTHROPIC_MODEL = 'claude-sonnet-5'

# Prompt caching bills reads at a tenth of the input rate and writes at a
# premium that depends on the retention asked for.
CACHE_READ_MULTIPLIER = 0.10
CACHE_WRITE_MULTIPLIERS = {'5m': 1.25, '1h': 2.00}

# Gridar never counts tokens before a generation, so the guard needs a stand-in.
# 3.2 characters per token is deliberately below the measured average for
# French: accented text tokenizes worse, and over-estimating the input is the
# safe direction. For an exact figure the caller has to hit Anthropic's
# count_tokens endpoint, which this module cannot do since it makes no calls.
CHARS_PER_TOKEN_FR = 3.2

# Worst case assumed when a caller prices a generation without saying how long
# it may run. Matches the default `max_tokens` of `article_generator.call_claude`.
ANTHROPIC_FALLBACK_MAX_TOKENS = 4000

# --------------------------------------------------------------------------
# Verdict thresholds
# --------------------------------------------------------------------------

# Warn while there is still room to react. Past this share of the daily cap the
# operator gets told; past the cap itself the call is refused.
WARN_AT_RATIO = 0.80

# The cap resets at local midnight, not UTC midnight: an operator in Quebec who
# sets a daily ceiling means their day, and a counter rolling over at 20 h reads
# as a bug. Timestamps stay UTC, only the grouping key is local.
BUDGET_TIMEZONE = 'America/Toronto'


def _resolve_tz():
    """Fall back to UTC rather than die if the tz database is missing.

    A budget guard that raises on import takes down every paid call with it.
    Losing the local rollover only shifts when the counter resets.
    """
    try:
        return ZoneInfo(BUDGET_TIMEZONE)
    except Exception:  # noqa: BLE001
        return timezone.utc


_TZ = _resolve_tz()


# --------------------------------------------------------------------------
# Storage interface (no implementation here, on purpose)
# --------------------------------------------------------------------------

class BudgetStore(Protocol):
    """What persistence has to provide for the guard to work.

    Deliberately not implemented in this module. The counter has to be read and
    incremented inside one Postgres transaction, otherwise two Railway instances
    both read 9.90 $ and both let a 0.50 $ call through. See the report for the
    model to create.
    """

    def spent_today(self, day: str, provider: str | None = None) -> float:
        """Dollars already committed on `day` (a `budget_day_key` value).

        `provider` None means every provider, for a global cap.
        """
        ...

    def record(self, entry: dict) -> float:
        """Persist a `format_ledger_entry` dict, return the new daily total.

        Must add `entry['billed_cost_usd']` to the counter for
        `entry['day']` / `entry['provider']` atomically.
        """
        ...


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------

def _money(value: float) -> str:
    """Quebec French money: space for thousands, comma for decimals.

    A single Serper call costs a tenth of a cent, so two decimals would print
    every one of them as "0,00 $ US" and hide the very drift being watched.
    """
    decimals = 4 if 0 < abs(value) < 0.01 else 2
    text = f'{value:,.{decimals}f}'.replace(',', ' ').replace('.', ',')
    return f'{text} $ US'


def _pct(value: float) -> str:
    return f'{round(value)} %'


def _round_money(value: float) -> float:
    return round(float(value), 6)


def budget_day_key(moment: datetime | None = None) -> str:
    """The YYYY-MM-DD the counter groups by, in Quebec local time.

    A naive datetime is read as UTC: everything Gridar stores is UTC, and
    guessing local on a naive value is how an hour of spending lands on the
    wrong day twice a year.
    """
    if moment is None:
        moment = datetime.now(timezone.utc)
    elif moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(_TZ).date().isoformat()


def _coerce_date(value) -> date:
    if value is None:
        return datetime.now(timezone.utc).astimezone(_TZ).date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _positive_int(value, default: int = 0) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, number)


# --------------------------------------------------------------------------
# estimate_cost
# --------------------------------------------------------------------------

def estimate_cost(provider: str, operation: str, **kwargs) -> dict:
    """Cost of a call before making it, in US dollars.

    Returns {provider, operation, label, known, cost_usd, basis, notes,
    tariffs_checked_on, source}. `known` is False when the operation or the
    model is absent from the tables; the cost is then the most expensive known
    entry for that provider, so an unrecognized call is never priced at zero.

    Serper kwargs: calls, results_per_call, plan.
    Anthropic kwargs: model, input_tokens or prompt_chars, output_tokens or
    max_tokens, cache_read_tokens, cache_write_tokens, cache_ttl, calls,
    on_date.

    Raises BudgetError on an unknown provider: that is a coding mistake, and a
    guard that silently prices an unknown provider at zero is not a guard.
    """
    key = (provider or '').strip().lower()
    if key == 'serper':
        return _estimate_serper(operation, **kwargs)
    if key == 'anthropic':
        return _estimate_anthropic(operation, **kwargs)
    raise BudgetError(
        f'Fournisseur inconnu : {provider!r}. Attendu "serper" ou "anthropic".'
    )


def _estimate_serper(operation: str, *, calls: int = 1,
                     results_per_call: int = SERPER_SHALLOW_MAX_RESULTS,
                     plan: str = DEFAULT_SERPER_PLAN, **_ignored) -> dict:
    slug = (operation or '').strip().lower()
    entry = SERPER_OPERATIONS.get(slug)
    known = entry is not None
    notes = []

    if entry is None:
        entry = max(SERPER_OPERATIONS.values(), key=lambda e: e['credits'])
        notes.append(
            f'Opération Serper inconnue ({operation!r}) : facturée au tarif du '
            'point de terminaison le plus cher, par prudence.'
        )

    plan_key = (plan or '').strip().lower()
    unit = SERPER_PLANS.get(plan_key)
    if unit is None:
        unit = SERPER_PLANS[DEFAULT_SERPER_PLAN]
        plan_key = DEFAULT_SERPER_PLAN
        notes.append(
            f'Forfait Serper inconnu ({plan!r}) : calcul fait sur le forfait '
            f'{DEFAULT_SERPER_PLAN}, le plus cher au crédit.'
        )

    n_calls = _positive_int(calls, 1)
    depth = min(max(_positive_int(results_per_call, SERPER_SHALLOW_MAX_RESULTS), 1),
                SERPER_MAX_RESULTS)

    # Serper bills one credit up to 10 results and two beyond, whatever the
    # endpoint. Gridar's plan refuses num > 10 anyway, so this branch mostly
    # guards against a future plan upgrade quietly doubling the bill.
    credits_each = entry['credits']
    if depth > SERPER_SHALLOW_MAX_RESULTS:
        credits_each = max(credits_each, SERPER_DEEP_CREDITS)
        notes.append(
            f'{depth} résultats demandés par appel : au-delà de '
            f'{SERPER_SHALLOW_MAX_RESULTS}, Serper compte '
            f"{SERPER_DEEP_CREDITS} crédits au lieu d'un."
        )

    total_credits = credits_each * n_calls
    return {
        'provider': 'serper',
        'operation': slug,
        'label': entry['label'],
        'known': known,
        'cost_usd': _round_money(total_credits * unit),
        'basis': {
            'calls': n_calls,
            'results_per_call': depth,
            'credits_per_call': credits_each,
            'credits_total': total_credits,
            'plan': plan_key,
            'usd_per_credit': unit,
        },
        'notes': notes,
        'tariffs_checked_on': TARIFFS_CHECKED_ON,
        'source': TARIFF_SOURCES['serper'],
    }


def _anthropic_rates(model: str, on_date: date):
    """(input_rate, output_rate, intro_applied, model_known) per million tokens."""
    entry = ANTHROPIC_MODELS.get(model)
    known = entry is not None
    if entry is None:
        entry = max(ANTHROPIC_MODELS.values(), key=lambda e: e['output'])

    intro = entry.get('intro')
    if intro and on_date <= date.fromisoformat(intro['until']):
        return intro['input'], intro['output'], True, known
    return entry['input'], entry['output'], False, known


def _estimate_anthropic(operation: str, *, model: str = DEFAULT_ANTHROPIC_MODEL,
                        input_tokens=None, prompt_chars=None,
                        output_tokens=None, max_tokens=None,
                        cache_read_tokens: int = 0, cache_write_tokens: int = 0,
                        cache_ttl: str = '5m', calls: int = 1,
                        on_date=None, **_ignored) -> dict:
    notes = []
    day = _coerce_date(on_date)
    model_key = (model or DEFAULT_ANTHROPIC_MODEL).strip()
    in_rate, out_rate, intro_applied, model_known = _anthropic_rates(model_key, day)

    if not model_known:
        notes.append(
            f'Modèle inconnu ({model!r}) : facturé au tarif du modèle le plus '
            'cher de la table, par prudence.'
        )
    elif intro_applied:
        until = ANTHROPIC_MODELS[model_key]['intro']['until']
        notes.append(
            f"Tarif de lancement appliqué pour {model_key}, valable jusqu'au "
            f'{until}. Après cette date le coût monte sans que rien ne change '
            'dans le code.'
        )

    # Input: an exact count if the caller has one, otherwise a character
    # approximation, otherwise nothing.
    if input_tokens is not None:
        n_in = _positive_int(input_tokens)
    elif prompt_chars is not None:
        n_in = math.ceil(_positive_int(prompt_chars) / CHARS_PER_TOKEN_FR)
        notes.append(
            f"Jetons d'entrée estimés à partir de {_positive_int(prompt_chars)} "
            f'caractères ({CHARS_PER_TOKEN_FR} caractères par jeton en français).'
        )
    else:
        n_in = 0
        notes.append(
            "Aucun décompte d'entrée fourni : l'entrée est comptée à zéro, "
            'le coût réel sera donc un peu plus élevé.'
        )

    # Output: the real cost driver. Without a signal, assume the worst case
    # rather than return zero, which would let a runaway loop through.
    output_known = True
    if output_tokens is not None:
        n_out = _positive_int(output_tokens)
    elif max_tokens is not None:
        n_out = _positive_int(max_tokens)
        notes.append(
            f'Sortie estimée au pire cas : les {n_out} jetons de max_tokens. '
            'Une réponse plus courte coûtera moins cher.'
        )
    else:
        n_out = ANTHROPIC_FALLBACK_MAX_TOKENS
        output_known = False
        notes.append(
            'Ni output_tokens ni max_tokens fournis : sortie supposée à '
            f'{ANTHROPIC_FALLBACK_MAX_TOKENS} jetons.'
        )

    ttl = cache_ttl if cache_ttl in CACHE_WRITE_MULTIPLIERS else '5m'
    n_cache_read = _positive_int(cache_read_tokens)
    n_cache_write = _positive_int(cache_write_tokens)

    per_call = (
        n_in / 1_000_000 * in_rate
        + n_out / 1_000_000 * out_rate
        + n_cache_read / 1_000_000 * in_rate * CACHE_READ_MULTIPLIER
        + n_cache_write / 1_000_000 * in_rate * CACHE_WRITE_MULTIPLIERS[ttl]
    )
    n_calls = _positive_int(calls, 1)

    return {
        'provider': 'anthropic',
        'operation': (operation or '').strip().lower(),
        'label': f'génération {model_key}',
        'known': model_known and output_known,
        'cost_usd': _round_money(per_call * n_calls),
        'basis': {
            'model': model_key,
            'calls': n_calls,
            'input_tokens': n_in,
            'output_tokens': n_out,
            'cache_read_tokens': n_cache_read,
            'cache_write_tokens': n_cache_write,
            'cache_ttl': ttl,
            'usd_per_mtok_input': in_rate,
            'usd_per_mtok_output': out_rate,
            'intro_rate_applied': intro_applied,
            'priced_on': day.isoformat(),
        },
        'notes': notes,
        'tariffs_checked_on': TARIFFS_CHECKED_ON,
        'source': TARIFF_SOURCES['anthropic'],
    }


# --------------------------------------------------------------------------
# check_budget
# --------------------------------------------------------------------------

def check_budget(spent_today: float, estimate: float, daily_cap: float) -> dict:
    """Verdict on one call: allow, warn or deny, with the French explanation.

    `spent_today` is what the counter already holds for the day, `estimate` the
    output of `estimate_cost`, `daily_cap` the ceiling in US dollars. Returns
    {decision, reason, spent_today_usd, estimate_usd, projected_usd,
    daily_cap_usd, remaining_usd, usage_pct, message}.

    Fails closed: a non-finite number anywhere denies the call, because the one
    situation this guard exists for is a loop producing nonsense.
    """
    values = {'spent_today': spent_today, 'estimate': estimate, 'daily_cap': daily_cap}
    for name, raw in values.items():
        try:
            values[name] = float(raw)
        except (TypeError, ValueError):
            values[name] = math.nan
    if not all(math.isfinite(v) for v in values.values()):
        return _verdict(
            'deny', 'invalid_input', 0.0, 0.0, 0.0,
            'Chiffres de budget invalides (valeur non numérique ou infinie). '
            "L'appel est bloqué par sécurité : c'est le signe qu'un "
            'compteur est corrompu.'
        )

    spent = max(0.0, values['spent_today'])
    cost = max(0.0, values['estimate'])
    cap = values['daily_cap']

    if cap <= 0:
        return _verdict(
            'deny', 'no_budget', spent, cost, cap,
            f"Aucun budget alloué aujourd'hui (plafond à {_money(max(cap, 0.0))}). "
            'Tout appel payant est bloqué tant que le plafond reste à zéro.'
        )

    projected = spent + cost
    remaining = max(0.0, cap - spent)

    if cost > cap:
        return _verdict(
            'deny', 'single_call_over_cap', spent, cost, cap,
            f'Cet appel coûte à lui seul {_money(cost)}, alors que le plafond '
            f'quotidien est de {_money(cap)}. Même sur une journée vide il ne '
            'passerait pas : réduis la demande (moins de mots-clés, moins de '
            'jetons) ou relève le plafond.'
        )

    if projected > cap:
        return _verdict(
            'deny', 'cap_exceeded', spent, cost, cap,
            f'Plafond quotidien atteint. {_money(spent)} déjà dépensés '
            f"aujourd'hui, cet appel en ajouterait {_money(cost)}, et le "
            f'plafond est de {_money(cap)}. Il reste {_money(remaining)}. '
            'Le compteur repart à minuit, heure du Québec.'
        )

    usage = projected / cap * 100
    if projected >= cap * WARN_AT_RATIO:
        return _verdict(
            'warn', 'approaching_cap', spent, cost, cap,
            f'Budget serré : {_money(projected)} sur {_money(cap)} une fois cet '
            f'appel fait, soit {_pct(usage)} du budget du jour. Il restera '
            f'{_money(max(0.0, cap - projected))}.'
        )

    return _verdict(
        'allow', 'ok', spent, cost, cap,
        f'Budget correct : {_money(projected)} sur {_money(cap)} après cet '
        f'appel, soit {_pct(usage)} du budget du jour.'
    )


def _verdict(decision: str, reason: str, spent: float, cost: float,
             cap: float, message: str) -> dict:
    projected = spent + cost
    safe_cap = max(0.0, cap)
    return {
        'decision': decision,
        'reason': reason,
        'spent_today_usd': _round_money(spent),
        'estimate_usd': _round_money(cost),
        'projected_usd': _round_money(projected),
        'daily_cap_usd': _round_money(safe_cap),
        'remaining_usd': _round_money(max(0.0, safe_cap - spent)),
        'usage_pct': round(projected / safe_cap * 100, 1) if safe_cap > 0 else None,
        'message': message,
    }


# --------------------------------------------------------------------------
# format_ledger_entry
# --------------------------------------------------------------------------

_LEDGER_STATUSES = ('ok', 'error', 'denied')


def format_ledger_entry(*, provider: str, operation: str, estimate: dict | None = None,
                        actual_cost_usd=None, status: str = 'ok',
                        decision: str | None = None, model: str | None = None,
                        quantity=None, occurred_at: datetime | None = None,
                        context: dict | None = None) -> dict:
    """The line to journal, ready to store. Pass `estimate` straight through.

    `billed_cost_usd` is the field the daily counter adds, and it is the whole
    point of this function: a call whose real cost never came back still has to
    move the counter, otherwise a provider that answers without a usage block
    reads as free and the guard never fires. A denied call bills zero; anything
    else bills the measured cost when there is one and the estimate otherwise.
    A failure that consumed nothing has to say so with actual_cost_usd=0.

    `day` is local (see BUDGET_TIMEZONE) because that is what the cap resets on;
    `occurred_at` stays UTC because that is what everything else in the app
    stores. The asymmetry is deliberate.
    """
    if status not in _LEDGER_STATUSES:
        raise BudgetError(
            f'Statut inconnu : {status!r}. Attendu {_LEDGER_STATUSES}.'
        )

    est = estimate or {}
    estimated = _round_money(est.get('cost_usd') or 0.0)

    if status == 'denied':
        billed = 0.0
    elif actual_cost_usd is not None:
        billed = _round_money(max(0.0, float(actual_cost_usd)))
    else:
        billed = estimated

    moment = occurred_at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    return {
        'day': budget_day_key(moment),
        'occurred_at': moment.astimezone(timezone.utc).isoformat(),
        'provider': (provider or '').strip().lower(),
        'operation': (operation or '').strip().lower(),
        'label': est.get('label') or '',
        'model': model or (est.get('basis') or {}).get('model') or '',
        'status': status,
        'decision': decision,
        'quantity': quantity if quantity is not None else est.get('basis'),
        'estimated_cost_usd': estimated,
        'actual_cost_usd': (
            _round_money(actual_cost_usd) if actual_cost_usd is not None else None
        ),
        'billed_cost_usd': billed,
        'estimate_known': bool(est.get('known', False)),
        'tariffs_checked_on': est.get('tariffs_checked_on', TARIFFS_CHECKED_ON),
        'context': dict(context or {}),
    }
