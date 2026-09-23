"""Guards that run before any request is sent (S0 spec §4.5). A guard failure sends nothing."""
from __future__ import annotations

import re

_FORBIDDEN_REQUEST = (
    (re.compile(r"<NATIVEMETHOD\b[^>]*>[^<]*\*[^<]*</NATIVEMETHOD\s*>", re.IGNORECASE),
     "`*` as a NATIVEMETHOD crashes Tally (LESSONS §5)"),
    (re.compile(r"<FETCH\b[^>]*>[^<]*\*[^<]*</FETCH\s*>", re.IGNORECASE),
     "`*` as a FETCH value crashes Tally (LESSONS §5)"),
    (re.compile(r"\$\$InDateRange", re.IGNORECASE), "$$InDateRange crashes TallyPrime 7 (LESSONS §3)"),
)

_STAR_ENTITY = re.compile(r"&#(?:0*42|x0*2a);", re.IGNORECASE)


class GuardError(Exception):
    """A guard refused; nothing was sent."""


def _decode_star_entities(xml: str) -> str:
    """A numeric character reference for `*` (decimal or hex, any case) decoded before matching."""
    return _STAR_ENTITY.sub("*", xml)


def check_request(xml: str) -> None:
    decoded = _decode_star_entities(xml)
    for pattern, reason in _FORBIDDEN_REQUEST:
        if pattern.search(decoded):
            raise GuardError(f"Request refused: {reason}")


def check_mutation_allowed(expected: str, *, mutating: bool) -> None:
    """The company-name half of the mutation guard, checked before any request (even the company-list guard) is sent."""
    if mutating and "Probe" not in expected:
        raise GuardError(f"Refusing to change {expected!r}: only companies with 'Probe' in the name may be changed.")


def check_company(loaded: list[str], expected: str, *, mutating: bool) -> None:
    """Exactly one company loaded, and it's the expected one. Changes only on companies named '…Probe…'."""
    if not loaded:
        raise GuardError(f"No company open in Tally. Open {expected!r}.")
    if len(loaded) > 1:
        raise GuardError(f"{len(loaded)} companies are loaded ({', '.join(loaded)}). Close all but {expected!r}.")
    if loaded[0] != expected:
        raise GuardError(f"Tally has {loaded[0]!r} open, but this step expects {expected!r}.")
    check_mutation_allowed(expected, mutating=mutating)
