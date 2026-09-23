import httpx

from v2.probes import p17_ledger_level_tb as p17
from v2.probes.core import Outcome
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import (COMPANY_A, ScriptedIO, a_tally, company_list_xml, make_harness, objects_xml,
                                   ready_store, tb_xml)

BASELINE = {"Capital Account": "1000.00", "Current Liabilities": "1834142.00", "Current Assets": "-1835142.00"}
LEDGERS = [{"Name": "Capital Account", "Parent": "Capital Account"},
           {"Name": "HP India Sales Pvt Ltd", "Parent": "Sundry Creditors"}, {"Name": "Cash", "Parent": "Cash-in-Hand"}]
GROUPS = [{"Name": "Capital Account", "Parent": "Primary"}, {"Name": "Current Liabilities", "Parent": "Primary"},
          {"Name": "Sundry Creditors", "Parent": "Current Liabilities"}, {"Name": "Current Assets", "Parent": "Primary"},
          {"Name": "Cash-in-Hand", "Parent": "Current Assets"}, {"Name": "Stock-in-Hand", "Parent": "Current Assets"}]
GROUP_TB = tb_xml([("Capital Account", "", "1000.00"), ("Current Liabilities", "", "1834142.00"),
                   ("Current Assets", "-1835142.00", "")])


def _exploded(hp="1834142.00"):
    return tb_xml([("Capital Account", "", "1000.00"), ("Capital Account", "", "1000.00"),
                   ("Current Liabilities", "", "1834142.00"), ("Sundry Creditors", "", "1834142.00"),
                   ("HP India Sales Pvt Ltd", "", hp), ("Current Assets", "-1835142.00", ""),
                   ("Cash-in-Hand", "-1835142.00", ""), ("Cash", "-1835142.00", "")])


def _explode_on_flag(hp="1834142.00"):
    return lambda body: _exploded(hp) if "<EXPLODEFLAG>Yes</EXPLODEFLAG>" in body else GROUP_TB


def _fake(tb_handler):
    fake, _ = a_tally()
    fake.route("S0P17Ledgers", lambda body: objects_xml("LEDGER", LEDGERS))
    fake.route("S0P17Groups", lambda body: objects_xml("GROUP", GROUPS))
    fake.route("<ID>Trial Balance</ID>", tb_handler)
    return fake


async def _run(tmp_path, fake):
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store, baseline=BASELINE)
    outcome = await run_probe(p17.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return outcome, store, store.probe_entry(17)["parts"]["A"]


async def test_explodeflag_gives_ledger_rows_and_is_confirmed(tmp_path):
    outcome, store, part = await _run(tmp_path, _fake(_explode_on_flag()))
    assert outcome is Outcome.CONFIRMED, part["summary"]
    candidates = part["observations"]["candidates"]
    assert part["observations"]["working_variable"] == "explodeflag"
    assert candidates["explodeflag"]["ledger_rows"] == 3
    assert candidates["explodeflag"]["stock_bearing_skipped"] == ["Current Assets"]
    assert candidates["isledgerwise"]["ledger_rows"] == 0
    assert store.confirmed("ledger_level_tb")["candidate"] == "explodeflag"
    assert "__COMPANY__" in store.confirmed("ledger_level_tb")["xml_template"]
    assert len([f for f in part["fixtures"] if f.startswith("p17_A_tb_exploded_")]) == len(p17.EXPLODE_CANDIDATES)


async def test_no_candidate_gives_ledger_rows_fails(tmp_path):
    outcome, store, part = await _run(tmp_path, _fake(lambda body: GROUP_TB))
    assert outcome is Outcome.FAILED
    assert "rung 2 stays group-level" in part["spec_impact"]
    assert store.confirmed("ledger_level_tb") is None


async def test_ledger_rows_that_do_not_sum_are_different(tmp_path):
    outcome, _, part = await _run(tmp_path, _fake(_explode_on_flag(hp="1834000.00")))
    assert outcome is Outcome.DIFFERENT
    assert "Current Liabilities" in part["observations"]["candidates"]["explodeflag"]["mismatches"]


async def test_a_candidate_that_hangs_tally_fails_and_stops(tmp_path):
    hung = {"yes": False}

    def tb(body):
        if "<EXPLODEFLAG>Yes</EXPLODEFLAG>" in body:
            hung["yes"] = True
            return httpx.ReadTimeout
        return GROUP_TB

    fake = _fake(tb)
    fake.route("<ID>List of Companies</ID>",
               lambda body: httpx.ReadTimeout if hung["yes"] else company_list_xml([COMPANY_A]))
    outcome, _, part = await _run(tmp_path, fake)
    assert outcome is Outcome.FAILED
    assert "unresponsive" in part["summary"] and "hang Tally" in part["spec_impact"]
    assert list(part["observations"]["candidates"]) == ["explodeflag"]
