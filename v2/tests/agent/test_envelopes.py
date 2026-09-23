import xml.etree.ElementTree as ET

import pytest

from v2.agent.tally.envelopes import build_company_list, esc, formula_string, wrap_collection, wrap_report

NAMES = ["A & B", "Sharma & Sons' Probe Traders", 'He said "x"', "a<b>c", "शर्मा ट्रेडर्स"]


@pytest.mark.parametrize("name", NAMES)
def test_collection_escapes_company(name):
    root = ET.fromstring(wrap_collection("C1", "Ledger", ["Name"], company=name))
    assert root.find(".//SVCurrentCompany").text == name


@pytest.mark.parametrize("name", NAMES)
def test_report_escapes_company(name):
    root = ET.fromstring(wrap_report("Trial Balance", "01-04-2025", "31-03-2026", company=name))
    assert root.find(".//SVCurrentCompany").text == name
    assert root.find(".//SVFROMDATE").text == "01-04-2025"
    assert root.find(".//SVTODATE").text == "31-03-2026"


def test_no_company_means_no_company_variable():
    assert ET.fromstring(wrap_collection("C1", "Ledger", ["Name"])).find(".//SVCurrentCompany") is None
    assert ET.fromstring(wrap_report("Trial Balance", "01-04-2025", "31-03-2026")).find(".//SVCurrentCompany") is None


def test_collection_filters_round_trip():
    xml = wrap_collection(
        "C2", "Voucher", ["GUID", "AlterID"],
        static_vars={"SVFROMDATE": "01-06-2023", "SVTODATE": "30-06-2023"},
        filters=[("S0Alt", "$AlterID > 5"), ("S0Date", '$Date < $$Date:"01-07-2023"')],
    )
    root = ET.fromstring(xml)
    assert [f.text for f in root.iter("FILTER")] == ["S0Alt", "S0Date"]
    systems = {s.get("NAME"): s.text for s in root.iter("SYSTEM")}
    assert systems == {"S0Alt": "$AlterID > 5", "S0Date": '$Date < $$Date:"01-07-2023"'}
    assert [m.text for m in root.iter("NATIVEMETHOD")] == ["GUID", "AlterID"]
    assert root.find(".//SVFROMDATE").text == "01-06-2023"


def test_invalid_static_variable_name_rejected():
    with pytest.raises(ValueError):
        wrap_collection("C3", "Ledger", ["Name"], static_vars={"SV DATE": "x"})


def test_build_company_list_shape():
    root = ET.fromstring(build_company_list())
    assert root.find(".//ID").text == "List of Companies"
    assert root.find(".//COLLECTION/TYPE").text == "Company"
    assert [m.text for m in root.iter("NATIVEMETHOD")] == ["Name"]


def test_esc_and_formula_string():
    assert esc("A & B's \"x\" <y>") == "A &amp; B&apos;s &quot;x&quot; &lt;y&gt;"
    assert formula_string("Bank Charges") == '"Bank Charges"'
    with pytest.raises(ValueError):
        formula_string('say "hi"')
