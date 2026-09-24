from collections import Counter
from datetime import date

import pytest

from v2.probes.company_b_view import (B_BOOKS_FROM, B_BOOKS_FROM_DATE, B_BOOKS_TO, compare_tags, dataset,
                                      expect_window, kind_label, loaded_licence, tag_of, voucher_rows)
from v2.probes.core import ProbeBlocked
from v2.tests.probes.fakes import vch, vouchers_xml

JUNE = (date(2023, 6, 1), date(2023, 6, 30))


def _rows(tags_and_days):
    return [{"tag": tag, "date": day} for tag, day in tags_and_days]


def test_tag_of_reads_the_loader_tag_and_nothing_else():
    assert tag_of("[S0-B:281] Sale to शर्मा ट्रेडर्स") == 281
    assert tag_of("  [S0-B:7] Receipt") == 7
    assert tag_of("S0-throwaway 1") is None
    assert tag_of("Paid [S0-B:9] later") is None
    assert tag_of("") is None
    assert (B_BOOKS_FROM, B_BOOKS_FROM_DATE, B_BOOKS_TO) == ("01-04-2022", date(2022, 4, 1), "31-03-2026")


def test_windows_follow_the_written_dataset():
    june = expect_window("educational", *JUNE)
    assert len(june.written) == 20 and not june.flagged and not june.skipped
    sep = expect_window("educational", date(2022, 9, 1), date(2022, 9, 30))
    assert len(sep.written) == 18 and sep.skipped == {101, 102}          # C36: the USD sales were never written
    feb = expect_window("educational", date(2023, 2, 1), date(2023, 2, 28))
    assert len(feb.written) == 20 and feb.flagged == {201, 202}         # cancelled: written, flagged
    assert feb.unflagged == frozenset(feb.written) - {201, 202}
    day = expect_window("educational", date(2023, 6, 1), date(2023, 6, 1))
    assert len(day.written) == 10                                        # Educational: the 1st and the 2nd only
    assert len(expect_window("licensed", date(2023, 6, 1), date(2023, 6, 1)).written) == 1


def test_fy2022_kind_mix_is_what_probe_21_weights_storage_by():
    fy = expect_window("educational", date(2022, 4, 1), date(2023, 3, 31))
    assert len(fy.written) == 238
    assert Counter(kind_label(v) for v in fy.written.values()) == Counter({
        "sales+inventory+bills": 81, "purchase+inventory+bills": 60, "receipt+bills": 40, "payment+bills": 24,
        "sales+inventory": 13, "payment": 12, "receipt": 8})
    assert dataset("educational") is dataset("educational")            # cached, generated once


def test_voucher_rows_read_tag_and_date_and_skip_the_cmpinfo_counter():
    text = vouchers_xml([vch({"DATE": "20230601", "NARRATION": "[S0-B:281] Sale"}),
                         vch({"DATE": "20230602", "NARRATION": "hand entry"})])
    assert voucher_rows(text) == [{"tag": 281, "date": date(2023, 6, 1)}, {"tag": None, "date": date(2023, 6, 2)}]


def test_an_exact_window_matches():
    june = expect_window("educational", *JUNE)
    result = compare_tags(_rows((t, v.date) for t, v in june.written.items()), june, *JUNE)
    assert result["match"] and result["bounded"]
    assert (result["returned"], result["expected_written"], result["expected_unflagged"]) == (20, 20, 20)
    assert result["date_span"] == ["2023-06-01", "2023-06-02"]


def test_compare_reports_missing_extra_untagged_and_duplicates():
    june = expect_window("educational", *JUNE)
    tags = sorted(june.written)
    rows = _rows([(t, date(2023, 6, 1)) for t in tags[1:]] + [(tags[1], date(2023, 6, 1)), (101, date(2023, 6, 1)),
                                                              (None, date(2023, 6, 2))])
    result = compare_tags(rows, june, *JUNE)
    assert not result["match"]
    assert result["missing"] == [tags[0]]
    assert result["extra"] == [101]                         # a skipped tag showing up is extra, never expected
    assert result["duplicates"] == [tags[1]]
    assert result["untagged"] == 1


def test_a_date_outside_the_window_is_not_bounded():
    june = expect_window("educational", *JUNE)
    rows = _rows([(t, v.date) for t, v in june.written.items()] + [(301, date(2023, 7, 1))])
    result = compare_tags(rows, june, *JUNE)
    assert not result["bounded"] and result["out_of_window"] == 1 and not result["match"]
    assert result["date_span"] == ["2023-06-01", "2023-07-01"]


def test_flagged_tags_are_recorded_but_never_decide_the_match():
    feb_window = (date(2023, 2, 1), date(2023, 2, 28))
    feb = expect_window("educational", *feb_window)
    with_flags = compare_tags(_rows((t, v.date) for t, v in feb.written.items()), feb, *feb_window)
    without_flags = compare_tags(_rows((t, feb.written[t].date) for t in feb.unflagged), feb, *feb_window)
    assert with_flags["match"] and with_flags["flagged_returned"] == [201, 202] and not with_flags["flagged_missing"]
    assert without_flags["match"] and without_flags["flagged_missing"] == [201, 202]


def test_loaded_licence_needs_a_clean_setup_b_and_a_recorded_licence():
    with pytest.raises(ProbeBlocked, match="setup-b"):
        loaded_licence({"licence": "educational"})
    with pytest.raises(ProbeBlocked, match="probe 0"):
        loaded_licence({"company_b_loaded_at": "2026-09-24T13:02:33+05:30"})
    assert loaded_licence({"licence": "educational", "company_b_loaded_at": "x"}) == "educational"
