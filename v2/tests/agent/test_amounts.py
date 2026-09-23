from decimal import Decimal

import pytest

from v2.agent.tally.amounts import AmountParseError, parse_decimal


@pytest.mark.parametrize("text,expected", [
    ("-1048846.53", Decimal("-1048846.53")),
    ("0", Decimal("0")),
    ("1,23,456.00", Decimal("123456.00")),
    ("  55856.21 ", Decimal("55856.21")),
])
def test_plain_numbers(text, expected):
    value = parse_decimal(text)
    assert value == expected
    assert isinstance(value, Decimal)


@pytest.mark.parametrize("text", [None, "", "   "])
def test_missing_is_none_not_zero(text):
    assert parse_decimal(text) is None


def test_forex_expression_raises_with_raw_text():
    raw = "-$1,000.00 @ ₹83.00/$ = -₹83,000.00"
    with pytest.raises(AmountParseError) as info:
        parse_decimal(raw)
    assert info.value.raw == raw
