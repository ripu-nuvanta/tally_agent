import os
import signal

import pytest

from v2.probes import p00_environment
from v2.probes.__main__ import main
from v2.probes.actions import Action
from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.core import Outcome, PartResult
from v2.probes.core import Probe
from v2.probes.operator.auto import AUTO_RUN_MODE, build_auto_operator
from v2.probes.operator.tally_control import TallyProcess
from v2.probes.registry import PROBES, load_probe
from v2.probes.report import render_report
from v2.probes.results import ResultsStore
from v2.tests.probes.fake_books import OWN_COMMAND, FakeBooks, FakeRunner, tmp_config, write_company_folder
from v2.tests.probes.fakes import FakeTally, ScriptedIO


def test_list_shows_every_probe_and_deferred(tmp_path, capsys):
    assert main(["--results", str(tmp_path / "r.json"), "list"]) == 0
    out = capsys.readouterr().out
    for item in PROBES:
        assert f"{item.id:>2}  {item.name}" in out
    assert out.count("⏭ deferred") == 2  # probes 9 and 20


def test_run_unbuilt_probe_returns_2(tmp_path, capsys):
    assert main(["--results", str(tmp_path / "r.json"), "run", "5"]) == 2
    assert "not built yet" in capsys.readouterr().out


def test_run_unknown_probe_id_returns_2(tmp_path, capsys):
    assert main(["--results", str(tmp_path / "r.json"), "run", "99"]) == 2
    assert "No probe 99 (probes are 0–25)." in capsys.readouterr().out


def test_run_unknown_part_returns_2(tmp_path, capsys):
    assert main(["--results", str(tmp_path / "r.json"), "run", "0", "--company", "B"]) == 2
    assert "Probe 0 has no part B (has A)." in capsys.readouterr().out


def test_company_with_first_is_a_parser_error(tmp_path):
    with pytest.raises(SystemExit):
        main(["--results", str(tmp_path / "r.json"), "run", "--first", "--company", "A"])


def test_first_order_stops_after_probe_0_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(p00_environment, "wine_version", lambda: "wine-9.0")
    fake = FakeTally([])
    results_path = tmp_path / "r.json"

    rc = main(["--results", str(results_path), "--fixtures", str(tmp_path / "fixtures"), "run", "--first"],
             transport=fake.transport(), io=ScriptedIO())

    assert rc == 0
    store = ResultsStore(results_path)
    assert store.probe_entry(0)["outcome"] == "BLOCKED"
    assert store.probe_entry(2) is None
    assert store.probe_entry(1) is None


def test_registry_matches_built_modules():
    ids = [item.id for item in PROBES]
    assert ids == list(range(26))
    for item in PROBES:
        probe = load_probe(item.id)
        if item.module is None:
            assert probe is None
            continue
        assert probe.id == item.id
        assert probe.name == item.name
        assert sorted(probe.part_labels) == sorted(item.companies.split("+"))
        assert set(probe.parts) <= set(probe.part_labels)


def test_report_rows_and_deferred(tmp_path):
    store = ResultsStore(tmp_path / "r.json")
    store.update_environment(wine="wine-9.0", tally_version="7.0", edition="Edit Log", licence="licensed")
    store.record_part(0, "A", PartResult(Outcome.CONFIRMED, "Tally answers | ok"), all_parts=["A"],
                      fixtures=[], manual_steps=[], ran_at=__import__("datetime").datetime(2026, 9, 23))
    store.record_part(1, "A", PartResult(Outcome.DIFFERENT, "AltVchId did not move", spec_impact="add fallback"),
                      all_parts=["A"], fixtures=[], manual_steps=[], ran_at=__import__("datetime").datetime(2026, 9, 23))
    text = render_report(store, "2026-09-23")
    assert "| wine | wine-9.0 |" in text
    assert "| 0 | environment | A | CONFIRMED | A: Tally answers \\| ok | — |" in text
    assert "| 1 | company_counters | A | DIFFERENT | A: AltVchId did not move | A: add fallback |" in text
    assert "| 3 | voucher_ids_flags | A+B | not run | — | — |" in text
    assert "- Probe 9 — chunk_latency" in text and "- Probe 20 — parity_cost" in text
    assert render_report(store, "2026-09-23") == text  # deterministic


def test_partial_probe_shows_remaining_parts(tmp_path, capsys):
    store = ResultsStore(tmp_path / "r.json")
    store.record_part(3, "A", PartResult(Outcome.CONFIRMED, "ok"), all_parts=["A", "B"], fixtures=[],
                      manual_steps=[], ran_at=__import__("datetime").datetime(2026, 9, 23))
    assert main(["--results", str(tmp_path / "r.json"), "list"]) == 0
    out = capsys.readouterr().out
    assert "PARTIAL (remaining: B)" in out
    text = render_report(store, "2026-09-23")
    assert "| 3 | voucher_ids_flags | A+B | PARTIAL (remaining: B) |" in text


def test_report_command_writes_file(tmp_path):
    out = tmp_path / "report.md"
    assert main(["--results", str(tmp_path / "r.json"), "report", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# S0 probe results")


def test_reset_a_resets_company_a_and_records_the_time(tmp_path, capsys):
    config = tmp_config(tmp_path)
    write_company_folder(config.seed_folder("A"), SEED_COMPANY)
    books = FakeBooks(config.company_folder("A"), running=False, loaded=False)
    op = build_auto_operator(config=config, transport=books.transport(), runner=FakeRunner(books, []),
                             echo=lambda line: None)
    assert main(["--results", str(tmp_path / "r.json"), "reset-a"], operator=op) == 0
    assert books.companies() == [COMPANIES["A"]]
    assert "company_a_reset_at" in ResultsStore(tmp_path / "r.json").environment
    assert "Company A reset" in capsys.readouterr().out


def test_reset_a_failure_returns_1(tmp_path, capsys):
    config = tmp_config(tmp_path)                       # no seed folder: the copy can't happen
    books = FakeBooks(config.company_folder("A"), running=False, loaded=False)
    op = build_auto_operator(config=config, transport=books.transport(), runner=FakeRunner(books, []),
                             echo=lambda line: None)
    assert main(["--results", str(tmp_path / "r.json"), "reset-a"], operator=op) == 1
    assert "reset-a failed" in capsys.readouterr().out


def test_run_auto_records_run_mode_and_tags_parts(tmp_path, monkeypatch):
    from v2.probes import __main__ as cli

    async def part(ctx):
        ctx.pause("Create it", Action("create_voucher", {"company": ctx.company_name, "ref": "c1", "ledger": "Electricity",
                                                         "amount": "1.00", "narration": "S0-throwaway cli"}))
        ctx.pause("Delete it", Action("delete_voucher", {"company": ctx.company_name, "ref": "c1"}))
        return PartResult(Outcome.CONFIRMED, "ok")

    probe = Probe(id=5, name="voucher_month_bounds", question="?", feeds=(), parts={"A": part})
    monkeypatch.setattr(cli, "load_probe", lambda pid: probe)
    books = FakeBooks(name=COMPANIES["A"])
    op = build_auto_operator(config=tmp_config(tmp_path), transport=books.transport(),
                             runner=FakeRunner(books, [TallyProcess(8, OWN_COMMAND)]), echo=lambda line: None)
    results = tmp_path / "r.json"
    rc = main(["--results", str(results), "--fixtures", str(tmp_path / "f"), "run", "5", "--auto"],
              transport=books.transport(), operator=op)
    assert rc == 0
    store = ResultsStore(results)
    assert store.environment["run_mode"] == AUTO_RUN_MODE
    assert store.probe_entry(5)["parts"]["A"]["observations"]["run_mode"] == "auto"
    assert books.state["vouchers"] == {}


def test_auto_with_non_interactive_is_a_parser_error(tmp_path):
    with pytest.raises(SystemExit):
        main(["--results", str(tmp_path / "r.json"), "--non-interactive", "run", "1", "--auto"])


def test_ctrl_c_during_a_blocking_wait_is_recorded_and_propagates(tmp_path, monkeypatch):
    """I2: signal.default_int_handler is installed for the duration of `run`, so an operator's Ctrl-C during a
    blocking pause surfaces as KeyboardInterrupt in run_probe, and the previous handler is restored afterwards."""
    from v2.probes import __main__ as cli

    async def part(ctx):
        ctx.pause("Blocking step", Action("close_all_companies"))
        return PartResult(Outcome.CONFIRMED, "unreachable")

    probe = Probe(id=5, name="voucher_month_bounds", question="?", feeds=(), parts={"A": part})
    monkeypatch.setattr(cli, "load_probe", lambda pid: probe)

    def on_wait(instruction):
        os.kill(os.getpid(), signal.SIGINT)

    io = ScriptedIO(on_wait=on_wait)
    previous_handler = signal.getsignal(signal.SIGINT)
    fake = FakeTally([COMPANIES["A"]])
    try:
        with pytest.raises(KeyboardInterrupt):
            main(["--results", str(tmp_path / "r.json"), "run", "5"], transport=fake.transport(), io=io)
    finally:
        assert signal.getsignal(signal.SIGINT) is previous_handler   # the previous handler wasn't leaked
    store = ResultsStore(tmp_path / "r.json")
    part_entry = store.probe_entry(5)["parts"]["A"]
    assert part_entry["outcome"] == "BLOCKED"
    assert "Interrupted by operator" in part_entry["summary"]
