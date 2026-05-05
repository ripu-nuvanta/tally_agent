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

def test_build_create_stock_item_18pct_rate():
    from backend.tally_bridge.import_builder import build_create_stock_item
    xml = build_create_stock_item(
        name="Samsung 24 inch Monitor",
        group="Electronics",
        uom="Nos",
        opening_qty=20,
        opening_rate=11000,
        hsn_code="8528",
        gst_rate=18,
        company="Bharat Traders Private Limited",
    )
    root = _root(xml)
    si = root.find(".//STOCKITEM")
    assert si.get("NAME") == "Samsung 24 inch Monitor"
    assert si.find("NAME.LIST/NAME").text == "Samsung 24 inch Monitor"
    assert si.findtext("PARENT") == "Electronics"
    assert si.findtext("BASEUNITS") == "Nos"
    assert si.findtext("HSNCODE") == "8528"
    assert si.findtext("HSN") == "8528"
    assert si.findtext("GSTAPPLICABLE") == "Applicable"
    assert si.findtext("GSTTYPEOFSUPPLY") == "Goods"

    # GSTDETAILS rates: 18% IGST, 9% CGST, 9% SGST
    gd = si.find("GSTDETAILS.LIST")
    assert gd.findtext("IGSTRATE") == "18"
    assert gd.findtext("CGSTRATE") == "9"
    assert gd.findtext("SGSTRATE") == "9"
    assert gd.findtext("TAXABILITY") == "Taxable"

    # Opening balance
    assert si.findtext("OPENINGBALANCE") == "20 Nos"
    assert si.findtext("OPENINGRATE") == "11000.00/Nos"
    assert si.findtext("OPENINGVALUE") == "220000.00"


def test_build_create_stock_item_12pct_rate_splits_correctly():
    from backend.tally_bridge.import_builder import build_create_stock_item
    xml = build_create_stock_item(
        name="A4 Paper Ream",
        group="Office Supplies",
        uom="Pcs",
        opening_qty=200,
        opening_rate=280,
        hsn_code="4802",
        gst_rate=12,
        company="X",
    )
    root = _root(xml)
    gd = root.find(".//GSTDETAILS.LIST")
    assert gd.findtext("IGSTRATE") == "12"
    assert gd.findtext("CGSTRATE") == "6"
    assert gd.findtext("SGSTRATE") == "6"

def test_build_create_ledger_with_opening_state_gstin():
    from backend.tally_bridge.import_builder import build_create_ledger
    xml = build_create_ledger(
        name="Apex Technologies Pvt Ltd",
        parent="North Zone Debtors",
        company="X",
        gstin="27AAACA0000A1Z5",
        state="Maharashtra",
        gst_reg_type="Regular",
        opening_balance=0,
        is_billwise=True,
    )
    root = _root(xml)
    led = root.find(".//LEDGER")
    assert led.findtext("PARTYGSTIN") == "27AAACA0000A1Z5"
    assert led.findtext("LEDSTATENAME") == "Maharashtra"
    assert led.findtext("GSTREGISTRATIONTYPE") == "Regular"
    assert led.findtext("ISBILLWISEON") == "Yes"


def test_build_create_ledger_with_opening_balance_only():
    from backend.tally_bridge.import_builder import build_create_ledger
    xml = build_create_ledger(
        name="Capital Account",
        parent="Capital Account",
        company="X",
        opening_balance=750000,
    )
    root = _root(xml)
    assert root.find(".//LEDGER").findtext("OPENINGBALANCE") == "750000.00"


def test_build_create_ledger_back_compat():
    """Existing call signature (positional + gstin only) still works."""
    from backend.tally_bridge.import_builder import build_create_ledger
    xml = build_create_ledger("Travel", "Indirect Expenses", "X")
    root = _root(xml)
    led = root.find(".//LEDGER")
    assert led.findtext("PARENT") == "Indirect Expenses"
    assert led.find("OPENINGBALANCE") is None  # not emitted when 0/None


def test_build_create_gst_ledger():
    from backend.tally_bridge.import_builder import build_create_gst_ledger
    xml = build_create_gst_ledger(
        name="CGST Output",
        duty_head="Central Tax",
        company="X",
    )
    root = _root(xml)
    led = root.find(".//LEDGER")
    assert led.get("NAME") == "CGST Output"
    assert led.findtext("PARENT") == "Duties & Taxes"
    assert led.findtext("TAXTYPE") == "GST"
    assert led.findtext("GSTDUTYHEAD") == "Central Tax"
    assert led.findtext("ISBILLWISEON") == "No"
    assert led.findtext("AFFECTSSTOCK") == "No"


