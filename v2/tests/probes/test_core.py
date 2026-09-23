import pytest

from v2.probes.core import Outcome, PartResult, combine

C, D, F, B = Outcome.CONFIRMED, Outcome.DIFFERENT, Outcome.FAILED, Outcome.BLOCKED


@pytest.mark.parametrize("parts,expected", [
    ({"A": C}, C),
    ({"A": C, "B": C}, C),
    ({"A": C, "B": D}, D),
    ({"A": C, "B": F}, F),
    ({"A": F, "B": D}, F),
    ({"A": B, "B": F}, B),
    ({"A": F, "B": None}, Outcome.PARTIAL),
    ({"A": C, "B": None}, Outcome.PARTIAL),
    ({}, Outcome.PARTIAL),
])
def test_combine_precedence(parts, expected):
    assert combine(parts) is expected


def test_different_and_failed_need_spec_impact():
    with pytest.raises(ValueError):
        PartResult(D, "x")
    with pytest.raises(ValueError):
        PartResult(F, "x", spec_impact="  ")
    assert PartResult(F, "x", spec_impact="fallback").spec_impact == "fallback"
    assert PartResult(C, "ok").spec_impact == ""
    assert PartResult(B, "timeout").outcome is B


def test_partial_is_never_a_part_outcome():
    with pytest.raises(ValueError):
        PartResult(Outcome.PARTIAL, "x")
