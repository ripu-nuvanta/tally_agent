from datetime import date
from decimal import Decimal
from pathlib import Path

from v2.probes.reads import (amount, ancestors, dmy, ledger_movements, parse_parents, parse_vouchers, postings,
                             primary_lines, qty_number, signed_ui_amount, stock_bearing_groups, stock_rows_any_depth,
                             tally_date, tb_rows_any_depth, top_group)
from v2.tests.probes.fakes import line, stock_summary_xml, vch, vouchers_xml

SYNC = Path(__file__).resolve().parents[1] / "fixtures" / "sync"
SALES = vouchers_xml([
    vch({"DATE": "20251001", "VOUCHERTYPENAME": "Sales", "MASTERID": "7"},
        lines=[line("Apex", "-118.00", bills=[{"NAME": "S001", "BILLTYPE": "New Ref", "AMOUNT": "-118.00"}],
                    _list="LEDGERENTRIES.LIST"),
               line("CGST Output", "18.00", _list="LEDGERENTRIES.LIST")],
        inventory=[{"STOCKITEMNAME": "HP Laptop 15s", "ACTUALQTY": " 1 Nos", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "100.00",
                    "accounting": [line("Sales - Electronics", "100.00")],
                    "batches": [{"GODOWNNAME": "Main Location", "AMOUNT": "100.00"}]}]),
])


def test_parse_vouchers_reads_header_lines_bills_inventory_and_skips_placeholders():
    [voucher] = parse_vouchers(SALES)                      # CMPINFO's <VOUCHER>0</VOUCHER> is skipped
    assert voucher["header"]["MASTERID"] == "7"
    assert [item["list"] for item in voucher["ledger_lines"]] == ["LEDGERENTRIES.LIST", "LEDGERENTRIES.LIST"]
    assert voucher["ledger_lines"][0]["bills"] == [{"NAME": "S001", "BILLTYPE": "New Ref", "AMOUNT": "-118.00"}]
    assert voucher["ledger_lines"][1]["bills"] == []        # the empty placeholder list is ignored
    assert voucher["inventory"][0]["fields"]["ACTUALQTY"] == "1 Nos"
    assert voucher["inventory"][0]["accounting"][0]["amount"] == Decimal("100.00")
    assert voucher["inventory"][0]["batches"] == [{"GODOWNNAME": "Main Location", "AMOUNT": "100.00"}]


def test_posting_rules():
    [voucher] = parse_vouchers(SALES)
    assert postings(voucher) == [("Apex", Decimal("-118.00")), ("CGST Output", Decimal("18.00")),
                                 ("Sales - Electronics", Decimal("100.00"))]
    assert postings(voucher, "all_only") == []
    assert sum(value for _, value in postings(voucher, "ledger_plus_alloc")) == 0
    [both] = parse_vouchers(vouchers_xml([vch({"DATE": "20251002"}, lines=[
        line("Cash", "-5.00"), line("Rent", "5.00"), line("Cash", "-5.00", _list="LEDGERENTRIES.LIST")])]))
    assert [name for name, _ in postings(both)] == ["Cash", "Rent"]      # ALLLEDGERENTRIES wins, never both lists
    assert [item["fields"]["LEDGERNAME"] for item in primary_lines(both)] == ["Cash", "Rent"]


def test_ledger_movements_skip_cancelled_optional_and_post_dated_and_respect_dates():
    vouchers = parse_vouchers(vouchers_xml([
        vch({"DATE": "20251001"}, lines=[line("Cash", "-10.00"), line("Rent", "10.00")]),
        vch({"DATE": "20251101"}, lines=[line("Cash", "-1.00"), line("Rent", "1.00")]),
        vch({"DATE": "20251005", "ISCANCELLED": "Yes"}, lines=[line("Cash", "-100.00"), line("Rent", "100.00")]),
        vch({"DATE": "20251006", "ISOPTIONAL": "Yes"}, lines=[line("Cash", "-100.00"), line("Rent", "100.00")]),
        vch({"DATE": "20260331", "ISPOSTDATED": "Yes"}, lines=[line("Cash", "-7.00"), line("Rent", "7.00")]),
    ]))
    assert ledger_movements(vouchers) == {"Cash": Decimal("-11.00"), "Rent": Decimal("11.00")}
    assert ledger_movements(vouchers, up_to=date(2025, 10, 31))["Cash"] == Decimal("-10.00")
    assert ledger_movements(vouchers, before=date(2025, 10, 1)) == {}
    assert ledger_movements(vouchers, include_post_dated=True)["Cash"] == Decimal("-18.00")


def test_dates_quantities_and_ui_amounts():
    assert tally_date("20251001") == date(2025, 10, 1)
    assert tally_date("1-Oct-25") == date(2025, 10, 1)
    assert tally_date("") is None
    assert dmy("31-10-2025") == date(2025, 10, 31)
    assert qty_number(" 25 Nos") == Decimal("25")
    assert qty_number("-2.0000 NOS") == Decimal("-2")
    assert qty_number("") is None
    assert signed_ui_amount("9,70,537.00 Dr") == Decimal("-970537.00")
    assert signed_ui_amount("1,000 Cr") == Decimal("1000")
    assert signed_ui_amount("-5") == Decimal("-5")
    assert signed_ui_amount("  ") is None
    assert amount("$100 @ ₹83/$ = ₹8300") is None             # a forex expression reads as missing, never zero


def test_group_walk_on_the_live_ledger_list():
    ledgers = parse_parents((SYNC / "p01_A_ledger_list.xml").read_text(encoding="utf-8"), "LEDGER")
    assert len(ledgers) == 35
    assert ledgers["Profit & Loss A/c"] == "Primary"          # exported as '&#4; Primary', sanitised
    assert ledgers["CGST Input"] == "Duties & Taxes"
    groups = {"North Zone Debtors": "Sundry Debtors", "Sundry Debtors": "Current Assets", "Current Assets": "Primary",
              "Duties & Taxes": "Current Liabilities", "Current Liabilities": ""}
    assert ancestors(ledgers["Apex Technologies Pvt Ltd"], groups) == ["North Zone Debtors", "Sundry Debtors",
                                                                        "Current Assets"]
    assert top_group(ledgers["CGST Input"], groups) == "Current Liabilities"
    assert top_group("Unknown Group", groups) == "Unknown Group"


def test_tb_rows_any_depth_on_the_live_tb():
    rows = tb_rows_any_depth((SYNC / "p00_A_anchors_tb.xml").read_text(encoding="utf-8"))
    assert [row["name"] for row in rows] == ["Capital Account", "Current Liabilities", "Current Assets",
                                              "Sales Accounts", "Purchase Accounts", "Indirect Expenses"]
    assert rows[2]["debit"] == Decimal("885263.00") and rows[2]["credit"] == Decimal("1719830.00")
    assert rows[1]["closing"] == Decimal("1757357.00")
    assert sum(row["closing"] for row in rows) == Decimal("3305800.00")    # live: the rows don't net to 0


def test_tb_and_stock_rows_any_depth_read_nested_rows():
    nested = ("<ENVELOPE><DSPACCNAME><DSPDISPNAME>Current Liabilities</DSPDISPNAME></DSPACCNAME><DSPACCINFO>"
              "<DSPCLCRAMT><DSPCLCRAMTA>10.00</DSPCLCRAMTA></DSPCLCRAMT><DSPEXPLOSION><DSPACCNAME>"
              "<DSPDISPNAME>HP India Sales Pvt Ltd</DSPDISPNAME></DSPACCNAME><DSPACCINFO><DSPCLCRAMT>"
              "<DSPCLCRAMTA>10.00</DSPCLCRAMTA></DSPCLCRAMT></DSPACCINFO></DSPEXPLOSION></DSPACCINFO></ENVELOPE>")
    assert [(r["name"], r["closing"]) for r in tb_rows_any_depth(nested)] == [
        ("Current Liabilities", Decimal("10.00")), ("HP India Sales Pvt Ltd", Decimal("10.00"))]
    stock = stock_rows_any_depth(stock_summary_xml([("Electronics", "60 Nos", "", "600000.00"),
                                                    ("Samsung 24 inch Monitor", "45 Nos", "11000.00/Nos", "495000.00")]))
    assert [(r["name"], r["qty"], r["value"]) for r in stock] == [
        ("Electronics", Decimal("60"), Decimal("600000.00")),
        ("Samsung 24 inch Monitor", Decimal("45"), Decimal("495000.00"))]


def test_stock_bearing_groups():
    assert stock_bearing_groups({"Stock-in-Hand": "Current Assets", "Current Assets": "Primary"}) == {"Current Assets"}
    assert stock_bearing_groups({}) == {"Current Assets"}
