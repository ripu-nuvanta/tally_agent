"""Decimal amounts for Tally values: never float, and a missing value is never silently zero.

New in v2 (Part 1 §13): the current parse_amount returns 0.0 for anything it can't parse, which turns a parse
failure into a legitimate-looking zero (a false parity match).
"""
from __future__ import annotations

import re
from decimal import Decimal

_PLAIN_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


class AmountParseError(ValueError):
    """The text is present but is not a plain number (e.g. a forex expression)."""

    def __init__(self, raw: str):
        super().__init__(f"Not a plain Tally amount: {raw!r}")
        self.raw = raw


def parse_decimal(text: str | None) -> Decimal | None:
    """'-1,048,846.53' → Decimal('-1048846.53'); '' or None → None; anything else raises AmountParseError."""
    if text is None or not text.strip():
        return None
    cleaned = text.strip().replace(",", "")
    if not _PLAIN_NUMBER.match(cleaned):
        raise AmountParseError(text)
    return Decimal(cleaned)
