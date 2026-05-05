"""Unit tests for new Stage 1 builders (Unit, StockGroup, StockItem, GST ledger,
Sales/Purchase/Receipt/Journal vouchers). Each test asserts XML structure only —
no live Tally calls."""
import xml.etree.ElementTree as ET

from backend.tally_bridge.import_builder import build_create_unit


def _root(xml: str) -> ET.Element:
    return ET.fromstring(xml)


def test_build_create_unit_has_no_name_list():
    xml = build_create_unit("Nos", formal_name="Numbers", company="Bharat Traders Private Limited")
    root = _root(xml)
    unit = root.find(".//UNIT")
    assert unit is not None
    assert unit.get("ACTION") == "Create"
    # NAME.LIST is forbidden on UNIT (causes "BAD UNIT NAME" per v4 doc)
    assert unit.find("NAME.LIST") is None
    assert unit.findtext("NAME") == "Nos"
    assert unit.findtext("ISSIMPLEUNIT") == "Yes"


def test_build_create_unit_uses_all_masters_report():
    xml = build_create_unit("Nos", formal_name="Numbers", company="Bharat Traders Private Limited")
    root = _root(xml)
    assert root.findtext(".//REPORTNAME") == "All Masters"
    assert root.findtext(".//SVCURRENTCOMPANY") == "Bharat Traders Private Limited"

def test_build_create_stock_group_has_name_list():
    from backend.tally_bridge.import_builder import build_create_stock_group
    xml = build_create_stock_group("Electronics", parent="", company="Bharat Traders Private Limited")
    root = _root(xml)
    sg = root.find(".//STOCKGROUP")
    assert sg.get("NAME") == "Electronics"
    assert sg.get("ACTION") == "Create"
    name_list = sg.find("NAME.LIST")
    assert name_list is not None
    assert name_list.findtext("NAME") == "Electronics"
    parent = sg.find("PARENT")
    assert parent is not None
    assert (parent.text or "") == ""
    assert sg.findtext("ISADDABLE") == "No"


def test_build_create_stock_group_with_parent():
    from backend.tally_bridge.import_builder import build_create_stock_group
    xml = build_create_stock_group("Sub Group", parent="Electronics", company="X")
    root = _root(xml)
    assert root.find(".//STOCKGROUP/PARENT").text == "Electronics"


