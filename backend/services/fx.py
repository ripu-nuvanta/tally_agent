"""Foreign-currency → INR conversion helpers.

All rate resolution and chat-override parsing is deterministic (no LLM math).
The single conversion point (amount × rate) lives in voucher_builder; this
module only resolves *which* rate to use and parses user rate overrides.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from backend.utils.currency_format import format_inr

_TWO_PLACES = Decimal("0.01")
# Matches the FX audit trail suffix appended by voucher_builder, e.g.
# " | FX: USD 100.00 @ ₹83.50 = ₹8,350.00". Strips any prior trail so a
# re-conversion appends exactly one.
_FX_TRAIL_RE = re.compile(r"\s*\|\s*FX:.*$")
# Warnings emitted for default/fallback/none rate sources (T6); removed on
# a user rate override since the rate is now explicit.
_RATE_WARNING_MARKERS = ("Used default", "No conversion rate")


def parse_default_rates(s: str) -> dict[str, float]:
    """Parse a config string like "USD:83.5,EUR:90" into a dict.

    Currency keys are uppercased. Malformed pairs (missing colon, missing or
    non-numeric rate) are skipped gracefully. Whitespace is tolerated.
    """
    rates: dict[str, float] = {}
    if not s:
        return rates
    for pair in s.split(","):
        if ":" not in pair:
            continue
        cur, _, rate_str = pair.partition(":")
        cur = cur.strip().upper()
        rate_str = rate_str.strip()
        if not cur or not rate_str:
            continue
        try:
            rates[cur] = float(rate_str)
        except ValueError:
            continue
    return rates


def resolve_fx_rate(
    currency: str,
    doc_rate: Decimal | None,
    override: Decimal | None,
    *,
    default_rates: dict[str, float],
    fallback: float,
) -> tuple[Decimal, str]:
    """Resolve the conversion rate and its source for a currency.

    Precedence: override > document > per-currency default > global fallback.
    - currency == "INR" (case-insensitive) → (Decimal("1"), "inr").
    - non-INR with nothing resolvable and fallback == 0 → (Decimal("0"), "none").

    Returns (rate, source) where source ∈
    {"override", "document", "default", "fallback", "inr", "none"}.
    """
    if currency.strip().upper() == "INR":
        return Decimal("1"), "inr"

    if override is not None:
        return Decimal(str(override)), "override"
    if doc_rate is not None:
        return Decimal(str(doc_rate)), "document"

    cur_default = default_rates.get(currency.strip().upper())
    if cur_default is not None:
        return Decimal(str(cur_default)), "default"

    if fallback:
        return Decimal(str(fallback)), "fallback"

    return Decimal("0"), "none"


# Keywords / symbols that signal a number immediately following (or, for "per
# <cur>", preceding) is an exchange rate. Anchored so plain text like
# "rate of return" or "interest rate is high" — no number adjacent — never matches.
_RATE_KEYWORD_PATTERNS = [
    # "use rate 84.5", "exchange rate 84", "rate 84.5", "rate = 84.5", "rate: 84.5"
    r"rate\s*[:=]?\s*(\d+(?:\.\d+)?)",
    # "convert at 84.5", "at 84.5"
    r"convert\s+at\s+(\d+(?:\.\d+)?)",
    r"\bat\s+(\d+(?:\.\d+)?)",
    # "@ 84.5"
    r"@\s*(\d+(?:\.\d+)?)",
    # "84.50 per usd"
    r"(\d+(?:\.\d+)?)\s+per\b",
]


def parse_rate_override(message: str) -> float | None:
    """Deterministically extract a rate override from a chat message.

    Matches phrasings like "use rate 84.5", "convert at 84.5", "rate = 84.5",
    "rate: 84.5", "@ 84.5", "84.50 per usd", "exchange rate 84". Returns the
    single float, or None if no rate-keyword-adjacent number is present.

    Plain text with no number adjacent to a rate keyword (e.g. "rate of return",
    "interest rate is high") returns None.
    """
    if not message:
        return None
    text = message.lower()
    for pattern in _RATE_KEYWORD_PATTERNS:
        m = re.search(pattern, text)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                continue
    return None


def _round_inr(amount: Decimal) -> float:
    """Round a Decimal to 2 dp (half-up) and return as float."""
    return float(amount.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP))


def recompute_entry_with_rate(entry: dict, rate: float) -> dict:
    """Recompute a pending voucher_review entry's INR amounts for a new FX rate.

    Pure function (does not mutate ``entry``). Recomputes from the entry's
    ORIGINAL foreign-currency fields (``original_amount`` /
    ``original_gst_entries``) — never by scaling the prior INR amount — so it is
    correct even from the no-rate "blocked" state (prior amount/fx_rate 0).

    - ``amount`` = round(original_amount × rate, 2).
    - each ``gst_entries[i].amount`` = round(original_gst_entries[i].amount × rate, 2),
      preserving the original ledger names/order.
    - ``fx_rate`` = rate.
    - narration: strip any prior ` | FX: ...` trail, then append a fresh one
      (same format as voucher_builder) for non-INR entries.
    - any prior default/no-rate warning is removed (rate is now user-set).
    - ``status`` reset to ``"draft"``.
    """
    out = dict(entry)
    rate_dec = Decimal(str(rate))

    original_amount = Decimal(str(entry.get("original_amount", 0)))
    inr_amount = _round_inr(original_amount * rate_dec)
    out["amount"] = inr_amount
    out["fx_rate"] = float(rate)

    original_gst = entry.get("original_gst_entries") or []
    out["gst_entries"] = [
        {"ledger": g["ledger"], "amount": _round_inr(Decimal(str(g["amount"])) * rate_dec)}
        for g in original_gst
    ]

    currency = str(entry.get("original_currency", "INR"))
    base_narration = _FX_TRAIL_RE.sub("", entry.get("narration", "")).rstrip()
    if currency.strip().upper() != "INR":
        base_narration += (
            f" | FX: {currency} {original_amount:.2f}"
            f" @ ₹{rate_dec:.2f} = {format_inr(inr_amount)}"
        )
    out["narration"] = base_narration

    out["warnings"] = [
        w for w in (entry.get("warnings") or [])
        if not any(w.startswith(marker) for marker in _RATE_WARNING_MARKERS)
    ]
    out["status"] = "draft"
    return out


# Words that signal the user is talking about the conversion rate, even without
# a number. Used to decide between "clarify" (rate words, no number) and
# "passthrough" (unrelated message → normal query path).
_RATE_INTENT_RE = re.compile(r"\b(rate|convert|exchange|fx|forex)\b", re.IGNORECASE)


def classify_pending_message(
    pending_entry: dict | None, message: str
) -> tuple[str, float | None]:
    """Decide how a chat message interacts with a pending voucher entry.

    Returns one of:
      - ``("override", rate)`` — a pending entry exists and the message parses
        as a rate override; recompute and return an updated review card.
      - ``("clarify", None)`` — a pending entry exists and the message mentions
        rate/conversion words but carries no number; ask for the number.
      - ``("passthrough", None)`` — no pending entry, or the message is unrelated
        to rates; run the normal query path unchanged.
    """
    if pending_entry is None:
        return ("passthrough", None)
    rate = parse_rate_override(message)
    if rate is not None:
        return ("override", rate)
    if message and _RATE_INTENT_RE.search(message):
        return ("clarify", None)
    return ("passthrough", None)
