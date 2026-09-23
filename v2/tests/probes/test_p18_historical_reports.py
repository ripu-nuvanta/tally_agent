from v2.probes import p18_historical_reports as p18
from v2.probes.core import Outcome
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import (ScriptedIO, a_tally, bills_xml, line, make_harness, objects_xml, ready_store,
                                   stock_summary_xml, tb_xml, vch, vouchers_xml)

LEDGERS = [
    {"Name": "Apex", "Parent": "Sundry Debtors", "OpeningBalance": ""},
    {"Name": "Samsung India Electronics", "Parent": "National Creditors", "OpeningBalance": ""},
    {"Name": "Cash", "Parent": "Cash-in-Hand", "OpeningBalance": "-1000.00"},
    {"Name": "Capital Account", "Parent": "Capital Account", "OpeningBalance": "1000.00"},
    {"Name": "Sales", "Parent": "Sales Accounts", "OpeningBalance": ""},
    {"Name": "Purchases", "Parent": "Purchase Accounts", "OpeningBalance": ""},
]
GROUPS = [
    {"Name": "Current Assets", "Parent": "Primary"}, {"Name": "Sundry Debtors", "Parent": "Current Assets"},
    {"Name": "Cash-in-Hand", "Parent": "Current Assets"}, {"Name": "Stock-in-Hand", "Parent": "Current Assets"},
    {"Name": "Current Liabilities", "Parent": "Primary"}, {"Name": "Sundry Creditors", "Parent": "Current Liabilities"},
    {"Name": "National Creditors", "Parent": "Sundry Creditors"}, {"Name": "Capital Account", "Parent": "Primary"},
    {"Name": "Sales Accounts", "Parent": "Primary"}, {"Name": "Purchase Accounts", "Parent": "Primary"},
]
MONITOR, TAB = "Samsung 24 inch Monitor", "Samsung Galaxy Tab A8"
VOUCHERS = vouchers_xml([
    vch({"DATE": "20250928", "VOUCHERTYPENAME": "Purchase"},
        lines=[line("Samsung India Electronics", "643100.00",
                    bills=[{"NAME": "P001", "BILLTYPE": "New Ref", "AMOUNT": "643100.00"}]),
               line("Purchases", "-643100.00")],
        inventory=[{"STOCKITEMNAME": MONITOR, "ISDEEMEDPOSITIVE": "Yes", "ACTUALQTY": "25 Nos", "AMOUNT": "-275000.00"}]),
    vch({"DATE": "20251001", "VOUCHERTYPENAME": "Sales"},
        lines=[line("Apex", "-110920.00", bills=[{"NAME": "S001", "BILLTYPE": "New Ref", "AMOUNT": "-110920.00"}]),
               line("Sales", "110920.00")],
        inventory=[{"STOCKITEMNAME": MONITOR, "ISDEEMEDPOSITIVE": "No", "ACTUALQTY": "5 Nos", "AMOUNT": "62500.00"}]),
    vch({"DATE": "20251020", "VOUCHERTYPENAME": "Receipt"},
        lines=[line("Cash", "-110920.00"),
               line("Apex", "110920.00", bills=[{"NAME": "S001", "BILLTYPE": "Agst Ref", "AMOUNT": "110920.00"}])]),
])
STOCK_ITEMS = [
    {"Name": MONITOR, "Parent": "Electronics", "BaseUnits": "Nos", "OpeningBalance": "20 Nos"},
    {"Name": TAB, "Parent": "Electronics", "BaseUnits": "Nos", "OpeningBalance": "15 Nos"},
]


def _tb(capital="1000.00", current_assets="-111920.00"):
    return tb_xml([("Capital Account", "", capital), ("Current Liabilities", "", "643100.00"),
                   ("Current Assets", current_assets, ""), ("Sales Accounts", "", "110920.00"),
                   ("Purchase Accounts", "-643100.00", "")])


def _fake(tb=None, monitor_qty="45 Nos"):
    fake, _ = a_tally()
    fake.route("S0P18Ledgers", lambda body: objects_xml("LEDGER", LEDGERS))
    fake.route("S0P18Groups", lambda body: objects_xml("GROUP", GROUPS))
    fake.route("S0P18Vouchers", lambda body: VOUCHERS)
    fake.route("S0P18Stock", lambda body: objects_xml("STOCKITEM", STOCK_ITEMS))
    fake.route("<ID>Trial Balance</ID>", lambda body: tb or _tb())
    fake.route("<ID>Bills Receivable</ID>", lambda body: "<ENVELOPE></ENVELOPE>")
    fake.route("<ID>Bills Payable</ID>", lambda body: bills_xml([("P001", "Samsung India Electronics", "643100.00")]))
    fake.route("<ID>Stock Summary</ID>", lambda body: stock_summary_xml([
        ("Electronics", "60 Nos", "", "697500.00"), (MONITOR, monitor_qty, "11000.00/Nos", "495000.00"),
        (TAB, "15 Nos", "13500.00/Nos", "202500.00")]))
    return fake


async def _run(tmp_path, fake):
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    outcome = await run_probe(p18.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return outcome, store.probe_entry(18)["parts"]["A"]


async def test_history_reads_match_the_lines(tmp_path):
    outcome, part = await _run(tmp_path, _fake())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert outcome is Outcome.PARTIAL                       # the B part comes in plan part 3
    assert part["observations"]["sub_verdicts"] == {"tb": "CONFIRMED", "bills_stock": "CONFIRMED"}
    assert part["observations"]["bills"]["receivable"]["weak"] is True
    assert part["observations"]["stock"]["item_rows"] == 2
    assert "p18_A_stock_summary_asof_2025-09-30.xml" in part["fixtures"]
    assert "Bills Receivable check is vacuous" in part["summary"]   # M12


async def test_tb_right_but_stock_wrong_fails_with_both_sub_verdicts(tmp_path):
    _, part = await _run(tmp_path, _fake(monitor_qty="40 Nos"))
    assert part["outcome"] == "FAILED"
    assert part["observations"]["sub_verdicts"] == {"tb": "CONFIRMED", "bills_stock": "FAILED"}
    assert "month-end comparison" in part["spec_impact"]
    assert "R30" not in part["spec_impact"]


async def test_tb_history_wrong_fails_with_r30(tmp_path):
    _, part = await _run(tmp_path, _fake(tb=_tb(capital="2000.00")))
    assert part["outcome"] == "FAILED"
    assert part["observations"]["sub_verdicts"]["tb"] == "FAILED"
    assert "R30" in part["spec_impact"]


async def test_stock_bearing_group_alone_does_not_fail_the_tb(tmp_path):
    _, part = await _run(tmp_path, _fake(tb=_tb(current_assets="-5.00")))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["tb"]["stock_bearing"]["Current Assets"]["match"] is False
