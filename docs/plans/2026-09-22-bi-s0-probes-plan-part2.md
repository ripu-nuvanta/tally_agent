# S0 Probes — Part 2 of 3: automated operator + company-A probes — Implementation Plan

> **Superseded fixture names (2026-09-24, plan part 5):** probe 18 A's bills/stock as-on date moved
> 30-09-2025 → 31-10-2025 (Ruling C43), and the untyped `vouchers_to_2025-10-31` read was replaced by an explicit
> whole-FY `vouchers_fy` fetch (Ruling C33/Q3). Every `p18_A_*_asof_2025-09-30.*` and `p18_A_vouchers_to_2025-10-31.*`
> name below is historical (this plan's own build-time record) — the byte-identical captures now live at
> [`v2/tests/fixtures/sync/c33_untyped_2026-09-23/`](../../v2/tests/fixtures/sync/c33_untyped_2026-09-23/), and the
> current fixture names are in `docs/specs/2026-09-22-bi-s0-probes-design.md` §11.5. This plan's task text is left
> as written (it records what was built at the time), not edited to match.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Tick each box in this file as soon as that step is verified** — not at the end (tracker rules).

**Goal:** Turn the throwaway live-run operator into tested v2 code (`run --auto`, `reset-a`), revise probe 1 so it
leaves company A as it was, and build the company-A probes 16, 17, 18, 19, 3, 4, 6, 12, 23, 25, 7, 8, 10, 13 (A parts)
with the anchors check inside ordered runs — all tested at tier A with a fake Tally — then run them live.

**Architecture:** Probes still talk to Tally only through `ProbeContext` (guarded, captured reads). Every `ctx.pause` /
`ctx.ask` now carries a machine-readable `Action`: the console shows the instruction text, while the new `AutoOperator`
(`v2/probes/operator/`) dispatches on `Action.kind` — XML writes through `v2/probes/setup/` (verified shapes, read back,
"Probe" companies only), open / close / restore through TallyPrime restarts under Wine behind an injectable
`ProcessRunner`. Multi-company probes are built with `parts={"A": run_a}` and `planned_parts=("A", "B")`, so they stay
PARTIAL until plan part 3 adds their B parts.

**Tech Stack:** Python ≥ 3.12, httpx (async client for probes, sync client for the operator, `MockTransport` for both in
tests), pytest + pytest-asyncio, uv.

**Spec:** [`docs/specs/2026-09-22-bi-s0-probes-design.md`](../specs/2026-09-22-bi-s0-probes-design.md) — §2 (S0-D9),
§4.2, §4.5, §5.8, §6, §7, §11, §12 (parent: [`2026-09-21-bi-part1-sync-design.md`](../specs/2026-09-21-bi-part1-sync-design.md)
§6, §12, §13). **Tracker:** [`2026-09-22-bi-part1-tracker.md`](2026-09-22-bi-part1-tracker.md) §3.

**Plan parts:**
- **Part 1 (done):** [`2026-09-22-bi-s0-probes-plan.md`](2026-09-22-bi-s0-probes-plan.md) — foundation + probes 0, 2, 1
  (run live 2026-09-22 with a throwaway operator script).
- **Part 2 (this file):** automated operator, probe 1 revision, company-A probes + the anchors steps, live run.
- **Part 3 (later file):** company-B dataset + `setup-b`, probes 5, 11, 14, 15, 21, 22, 24, the B parts of 3, 16, 18,
  23, 25, and company C.

## Global Constraints

- **Nothing outside `v2/` and `docs/` is created or changed.** No edits to `backend/`, `frontend/`, `tests/`,
  `scripts/`, `seed_data/` (read-only source for `reset-a`), root `pyproject.toml`, root `.gitignore`.
- **v2 never imports** `backend`, `scripts` or `tests`; `v2/agent/` never imports `v2.probes`; probe modules
  (`v2/probes/pNN_*.py`) never import `v2.probes.setup` or `v2.probes.operator` (Task 4 adds that test).
- **Copied write code lives only in `v2/probes/setup/`.** Every copied file's **first line** is
  `# Copied from: <source path> @ c04d7d2`, second line starts `# Changes:`.
- Money is `Decimal`, never float; a missing amount is `None`, never `0`.
- No request may contain `*` as a `NATIVEMETHOD`/`FETCH` value or `$$InDateRange` (reads go through `ctx.send/try_send`,
  writes through `TallyWriter.post`; both run `safety.check_request`).
- **One request at a time; default timeout 30 s, max 90 s; no automatic retries** (the operator's company-list polling
  while Tally loads is waiting, not retrying a probe request).
- **Writes** happen only inside the operator via `v2/probes/setup/` helpers, only to companies with "Probe" in the name
  (sole exception: renaming the fresh seed copy to company A on the operator's own `s0probe` Tally), use only verified
  shapes, are **read back** (LESSONS §12), and never "clear a field" (an empty-value alter is silently ignored — live
  2026-09-22). Throwaway vouchers are dated **31-Mar-2026** (Educational mode allows only the 1st, 2nd or 31st), narration
  starts `S0-throwaway`, and are deleted by Master ID in the same part; each has an `on_abort` cleanup note while in flight.
- **Tests never start Wine or touch the real Tally:** process control goes through `ProcessRunner`; tests use
  `FakeRunner` + `FakeBooks` / `FakeTally` over `httpx.MockTransport`.
- Commands run from the repo root (`/Users/nuvanta-mac-3/work/Tally prime`):
  - tests: `uv run --project v2 pytest v2/tests -q`
  - runner: `uv run --project v2 python -m v2.probes …`
- **No git commits** in this plan (the user commits when they choose).

## Live facts this plan relies on (2026-09-22)

- TallyPrime 7.0 Edit Log under Wine 11.0, **Educational**; Tally's current date 1-Mar-2026; company A's books
  1-Apr-2025 → 31-Mar-2026; last entry 1-Mar-2026. Company A's GUID `710de34a-3661-4a7b-8148-c2206c3b3e17`.
- Every start that loads a company stops on a licence box until a person clicks **T**; a start without a company needs no
  click; loading a company can block the XML server for more than 30 s.
- `tally.ini` `Load=` is ignored; `tally.exe /DATA:C:\users\Public\TallyPrimeEditLog\s0probe /LOAD:100003` works.
  Wine: `/Applications/Wine Stable.app/Contents/Resources/wine/bin/wine`; Tally dir
  `~/.wine/drive_c/Program Files/TallyPrimeEditLog`; data `~/.wine/drive_c/users/Public/TallyPrimeEditLog/s0probe`.
- Company rename: `<COMPANY NAME="old" ACTION="Alter"><NAME>new</NAME></COMPANY>` in an "All Masters" import (the
  `NAME.LIST` variant answers ALTERED=1 and does nothing). Payment via `ALLLEDGERENTRIES.LIST` + `Accounting Voucher View`
  returns `LASTVCHID` (= Master ID); header alter by Master ID works; delete by Master ID with `DATE="31-Mar-2026"` works
  (DELETED=1, AltVchId +3); `LastVoucherDate` is not rolled back. Ledger delete / rename shapes: v4 doc.
- Company A has no "Bank Charges"; its first Indirect Expenses ledger is "Electricity" (still carries EMAIL
  `s0probe@example.com` from the throwaway run — `reset-a` clears it).
- `$$LicenseInfo` / `IsEducationalMode` via `TYPE=Function` answered `<RESULT>Yes</RESULT>`; the XML header carried
  PRODMAJORREL 7 / PRODMINORREL 0.
- The live TB (`v2/tests/fixtures/sync/p00_A_anchors_tb.xml`) exports **Current Assets with both** `DSPCLDRAMTA 885263.00`
  and `DSPCLCRAMTA 1719830.00` positive, and its six group rows net to ₹33,05,800, not 0. Group comparisons therefore
  treat the stock-bearing group separately (Tasks 6–8).

## Conventions for this part

- **Step names** are the spec §11.5 names without the company prefix (the step regex allows no capitals): the table's
  `A_ledgers_asof_2025-10-31` is step `ledgers_asof_2025-10-31`, file `p16_A_ledgers_asof_2025-10-31.xml`. Steps a probe
  needs beyond §11.5 are listed in its task under "Extra steps" (Task 13 writes them into the spec).
- **Candidate** Tally names (spec §7 *candidate*) are module constants named `*_CANDIDATES` / `*_CANDIDATE`; each probe
  records which came back.
- `a_tally()`, `ready_store()`, `vch()`, `line()`, `vouchers_xml()`, `stock_summary_xml()` are test helpers added to
  `v2/tests/probes/fakes.py` in Task 6; `FakeBooks` / `FakeRunner` / `tmp_config` live in
  `v2/tests/probes/fake_books.py` (Tasks 2–3).

---

### Task 1: Harness changes — actions on pauses/asks, planned parts, run mode, anchors steps

**Files:**
- Create: `v2/probes/actions.py`
- Modify: `v2/probes/core.py`, `v2/probes/console.py`, `v2/probes/context.py`, `v2/probes/anchors.py`,
  `v2/probes/results.py`, `v2/probes/registry.py`, `v2/probes/runner.py`, `v2/probes/report.py`,
  `v2/probes/p00_environment.py`, `v2/probes/p02_active_company_guid.py`
- Modify tests: `v2/tests/probes/fakes.py`, `v2/tests/probes/test_cli.py` (registry test)
- Test: `v2/tests/probes/test_part2_harness.py`

**Interfaces:**
- Produces:
  - `actions`: `Action(kind: str, params: dict = {})` (frozen; unknown kind → `ValueError`), `PAUSE_KINDS`, `ASK_KINDS`
  - `core.Probe(..., planned_parts: tuple[str, ...] = ())` with property `part_labels -> tuple[str, ...]`
  - `console.ProbeIO.wait(instruction, action=None)`, `.ask(prompt, action=None)`; `ConsoleIO.run_mode = "manual"`
  - `ProbeContext.pause(instruction, action=None)`, `.ask(prompt, action=None)` (manual step gets `"action": kind`),
    property `run_mode -> str`
  - `anchors.check_anchors_direct(client, company, tb_baseline) -> AnchorResult` (uncaptured, guarded)
  - `ResultsStore.record_anchor_check(*, when, label, ok, problems, receivable, payable, ran_at)`, property `anchor_checks`
  - `registry.ANCHORS_BEFORE_PARITY = "anchors:before_parity"`, `ANCHORS_AFTER_A = "anchors:after_a_batch"`,
    `OrderStep = tuple[int | str, str]`, `is_anchor_step(step) -> bool`
  - `runner.run_anchor_check(step, label, *, client, store, io) -> bool`; `run_order` handles anchor steps, skips
    unbuilt parts before switching; `run_probe` records `all_parts=probe.part_labels` and tags
    `observations["run_mode"] = "auto"` when `io.run_mode == "auto"`
  - `fakes.ScriptedIO(answers=None, interactive=True, on_wait=None, on_action=None, answers_by_kind=None, run_mode="manual")`
    with `.actions`, `.ask_actions`; `FakeTally` answers `GET` with "TallyPrime Server is Running"

- [x] **Step 0: Record the baseline**

Run: `uv run --project v2 pytest v2/tests -q 2>&1 | tail -3`
Expected: all pass (146 at the end of part 1). Write the number down as **BASE**; later tasks give counts relative to it.

- [x] **Step 1: Write the failing tests** — `v2/tests/probes/test_part2_harness.py`

```python
"""Plan part 2 harness changes: actions on pause/ask, planned parts, unbuilt parts, run_mode, anchors steps."""
from datetime import datetime
from decimal import Decimal

import pytest

from v2.probes import p00_environment
from v2.probes import p02_active_company_guid as p02
from v2.probes import runner as runner_module
from v2.probes.actions import ASK_KINDS, PAUSE_KINDS, Action
from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.registry import ALL_ORDER, ANCHORS_AFTER_A, ANCHORS_BEFORE_PARITY, FIRST_ORDER
from v2.probes.report import render_report
from v2.probes.results import ResultsStore
from v2.probes.runner import run_order, run_probe
from v2.tests.probes.fakes import FakeTally, ScriptedIO, bills_xml, make_harness, mark_done, objects_xml, tb_xml

A = COMPANIES["A"]
RECEIVABLE = bills_xml([("S015", "Apex Technologies Pvt Ltd", "-62800.00"), ("S010", "Rest", "-907737.00")])
PAYABLE = bills_xml([("P001", "Samsung India Electronics", "243100.00"), ("P004", "Rest", "1591042.00")])
TB = tb_xml([("Capital Account", "", "100000.00"), ("Current Assets", "-100000.00", "")])
BASELINE = {"Capital Account": "100000.00", "Current Assets": "-100000.00"}


def _probe(parts, **kw):
    kw.setdefault("id", 99)
    return Probe(name="fake", question="?", feeds=(), parts=parts, **kw)


async def _ok(ctx):
    return PartResult(Outcome.CONFIRMED, "ok")


def test_action_kinds_are_validated():
    assert Action("open_company", {"label": "A"}).params == {"label": "A"}
    assert Action("close_all_companies") == Action("close_all_companies")
    with pytest.raises(ValueError):
        Action("make_coffee")
    assert not PAUSE_KINDS & ASK_KINDS


async def test_pause_and_ask_pass_actions_and_log_their_kind(tmp_path):
    async def part(ctx):
        ctx.pause("Create it", Action("create_voucher", {"ref": "r"}))
        ctx.observe("typed", ctx.ask("Balance?", Action("ui_closing_balance", {"ledger": "Cash"})))
        return PartResult(Outcome.CONFIRMED, "ok")

    client, store, capture = make_harness(tmp_path, FakeTally([A]))
    io = ScriptedIO(answers_by_kind={"ui_closing_balance": "12.00 Dr"})
    await run_probe(_probe({"A": part}), labels=None, client=client, store=store, capture=capture, io=io)
    steps = store.probe_entry(99)["parts"]["A"]["manual_steps"]
    assert [a.kind for a in io.actions] == ["create_voucher"]
    assert [a.kind for a in io.ask_actions] == ["ui_closing_balance"]
    assert [s["action"] for s in steps] == ["create_voucher", "ui_closing_balance"]
    assert steps[1]["input"] == "12.00 Dr"


async def test_pause_with_an_ask_kind_is_a_harness_error(tmp_path):
    async def part(ctx):
        ctx.pause("Type it", Action("licence"))
        return PartResult(Outcome.CONFIRMED, "unreachable")

    client, store, capture = make_harness(tmp_path, FakeTally([A]))
    await run_probe(_probe({"A": part}), labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    assert "is not a pause action" in store.probe_entry(99)["parts"]["A"]["summary"]


async def test_planned_parts_keep_a_one_part_probe_partial(tmp_path):
    client, store, capture = make_harness(tmp_path, FakeTally([A]))
    outcome = await run_probe(_probe({"A": _ok}, planned_parts=("A", "B")), labels=None, client=client, store=store,
                              capture=capture, io=ScriptedIO())
    assert outcome is Outcome.PARTIAL
    assert store.probe_entry(99)["parts"]["A"]["outcome"] == "CONFIRMED"
    assert store.probe_entry(99)["remaining"] == ["B"]


def test_built_parts_must_be_planned():
    with pytest.raises(ValueError):
        _probe({"C": _ok}, planned_parts=("A", "B"))


async def test_run_order_skips_an_unbuilt_part_without_switching(tmp_path, monkeypatch):
    async def part(ctx):
        raise AssertionError("should not run")

    probe = _probe({"A": part}, planned_parts=("A", "B"))
    monkeypatch.setattr(runner_module, "load_probe", lambda pid: probe)
    client, store, capture = make_harness(tmp_path, FakeTally([A]))
    io = ScriptedIO()
    await run_order([(99, "B")], client=client, store=store, capture=capture, io=io)
    assert io.waits == []
    assert "--- probe 99 part B: not built yet, skipped" in io.said


async def test_ordered_switch_carries_an_open_company_action(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_module, "load_probe", lambda pid: _probe({"A": _ok}))
    client, store, capture = make_harness(tmp_path, FakeTally([A]))
    io = ScriptedIO()
    await run_order([(99, "A")], client=client, store=store, capture=capture, io=io)
    assert io.actions == [Action("open_company", {"label": "A"})]


async def test_failed_switch_stops_the_order(tmp_path, monkeypatch):
    def refuse(action):
        raise ProbeBlocked("Tally won't start")

    monkeypatch.setattr(runner_module, "load_probe", lambda pid: _probe({"A": _ok}))
    client, store, capture = make_harness(tmp_path, FakeTally([A]))
    io = ScriptedIO(on_action=refuse)
    await run_order([(99, "A")], client=client, store=store, capture=capture, io=io)
    assert store.probe_entry(99) is None
    assert any(s.startswith("Stopped: couldn't switch Tally to company A") for s in io.said)


async def test_auto_run_mode_is_tagged_on_each_part(tmp_path):
    client, store, capture = make_harness(tmp_path, FakeTally([A]))
    await run_probe(_probe({"A": _ok}), labels=None, client=client, store=store, capture=capture,
                    io=ScriptedIO(run_mode="auto"))
    assert store.probe_entry(99)["parts"]["A"]["observations"]["run_mode"] == "auto"
    await run_probe(_probe({"A": _ok}, id=98), labels=None, client=client, store=store, capture=capture,
                    io=ScriptedIO())
    assert "run_mode" not in store.probe_entry(98)["parts"]["A"]["observations"]


def _anchor_fake(receivable=RECEIVABLE):
    fake = FakeTally([A])
    fake.route("<ID>Bills Receivable</ID>", lambda body: receivable)
    fake.route("<ID>Bills Payable</ID>", lambda body: PAYABLE)
    fake.route("<ID>Trial Balance</ID>", lambda body: TB)
    return fake


async def test_anchor_step_passes_records_and_continues(tmp_path, monkeypatch):
    calls = []

    async def part(ctx):
        calls.append(1)
        return PartResult(Outcome.CONFIRMED, "ok")

    monkeypatch.setattr(runner_module, "load_probe", lambda pid: _probe({"A": part}))
    client, store, capture = make_harness(tmp_path, _anchor_fake())
    store.update_environment(company_a_tb_baseline=BASELINE)
    io = ScriptedIO()
    await run_order([(ANCHORS_BEFORE_PARITY, "A"), (99, "A")], client=client, store=store, capture=capture, io=io)
    assert calls == [1]
    check = store.anchor_checks[-1]
    assert check["ok"] is True and check["when"] == "before_parity"
    assert check["receivable"] == Decimal("970537.00")
    assert "--- anchors check (before_parity) company A: OK" in io.said
    assert io.actions == [Action("open_company", {"label": "A"})]          # one switch, before the anchors step
    fixtures = tmp_path / "fixtures"
    assert not fixtures.exists() or not any("anchors" in p.name for p in fixtures.iterdir())


async def test_anchor_failure_stops_the_order(tmp_path, monkeypatch):
    calls = []

    async def part(ctx):
        calls.append(1)
        return PartResult(Outcome.CONFIRMED, "ok")

    monkeypatch.setattr(runner_module, "load_probe", lambda pid: _probe({"A": part}))
    client, store, capture = make_harness(tmp_path, _anchor_fake(bills_xml([("S015", "Apex", "-1.00")])))
    store.update_environment(company_a_tb_baseline=BASELINE)
    io = ScriptedIO()
    await run_order([(ANCHORS_AFTER_A, "A"), (99, "A")], client=client, store=store, capture=capture, io=io)
    assert calls == []
    assert store.anchor_checks[-1]["ok"] is False
    assert "Bills Receivable" in store.anchor_checks[-1]["problems"][0]
    assert any(s.startswith("Stopped: company A failed the anchors check.") for s in io.said)


async def test_anchor_step_without_baseline_stops(tmp_path):
    client, store, capture = make_harness(tmp_path, _anchor_fake())
    io = ScriptedIO()
    await run_order([(ANCHORS_BEFORE_PARITY, "A")], client=client, store=store, capture=capture, io=io)
    assert store.anchor_checks[-1]["problems"] == ["No TB baseline yet: run probe 0 first."]


async def test_anchor_step_with_wrong_company_open_stops(tmp_path):
    fake = _anchor_fake()
    fake.companies = ["Other Co"]
    client, store, capture = make_harness(tmp_path, fake)
    store.update_environment(company_a_tb_baseline=BASELINE)
    await run_order([(ANCHORS_BEFORE_PARITY, "A")], client=client, store=store, capture=capture, io=ScriptedIO())
    assert store.anchor_checks[-1]["problems"][0].startswith("GuardError:")


def test_orders_check_anchors_before_parity_and_after_the_a_batch():
    assert ALL_ORDER.index((ANCHORS_BEFORE_PARITY, "A")) == ALL_ORDER.index((16, "A")) - 1
    assert ALL_ORDER.index((ANCHORS_AFTER_A, "A")) == ALL_ORDER.index((13, "A")) + 1
    assert FIRST_ORDER.index((ANCHORS_BEFORE_PARITY, "A")) == FIRST_ORDER.index((16, "A")) - 1
    assert FIRST_ORDER.index((ANCHORS_AFTER_A, "A")) == FIRST_ORDER.index((18, "A")) + 1


def test_report_shows_run_mode_and_anchor_checks(tmp_path):
    store = ResultsStore(tmp_path / "r.json")
    store.update_environment(run_mode="auto (S0-D9)")
    store.record_anchor_check(when="before_parity", label="A", ok=False, problems=["Bills Receivable 1 ≠ 970537.00"],
                              receivable=Decimal("1"), payable=None, ran_at=datetime(2026, 9, 23, 10, 0))
    text = render_report(store, "2026-09-23")
    assert "| run_mode | auto (S0-D9) |" in text
    assert "| 2026-09-23T10:00:00 | before_parity | FAILED | Bills Receivable 1 ≠ 970537.00 |" in text
    assert "No anchors check has run yet." in render_report(ResultsStore(tmp_path / "e.json"), "2026-09-23")


async def test_p00_pauses_and_asks_carry_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(p00_environment, "wine_version", lambda: "wine-9.0")
    fake = FakeTally([])
    fake.route("S0CompanyGuid", lambda body: objects_xml(
        "COMPANY", [{"Name": fake.companies[0], "GUID": "g"}] if fake.companies else []))
    fake.route("<ID>Bills Receivable</ID>", lambda body: RECEIVABLE)
    fake.route("<ID>Bills Payable</ID>", lambda body: PAYABLE)
    fake.route("<ID>Trial Balance</ID>", lambda body: TB)

    def on_action(action):
        if action.kind == "restore_seed":
            fake.companies = [SEED_COMPANY]
        elif action.kind == "rename_company":
            fake.companies = [action.params["to"]]

    io = ScriptedIO(on_action=on_action, answers_by_kind={
        "data_folder": r"C:\s0probe\100003", "tally_version": "TallyPrime 7.0", "edition": "Edit Log",
        "licence": "educational"})
    client, store, capture = make_harness(tmp_path, fake)
    outcome = await run_probe(p00_environment.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    assert outcome is Outcome.CONFIRMED, store.probe_entry(0)["parts"]["A"]["summary"]
    assert [a.kind for a in io.actions] == ["tally_running", "restore_seed", "rename_company"]
    assert io.actions[2].params == {"from": SEED_COMPANY, "to": A}
    assert [a.kind for a in io.ask_actions] == ["data_folder", "tally_version", "edition", "licence"]


async def test_p02_pauses_carry_actions(tmp_path):
    fake = FakeTally([A])
    fake.route("S0ActiveCompany", lambda body: objects_xml(
        "COMPANY", [{"Name": A, "GUID": "g-1"}] if fake.companies else []))

    def on_action(action):
        fake.companies = [] if action.kind == "close_all_companies" else [A]

    io = ScriptedIO(on_action=on_action)
    client, store, capture = make_harness(tmp_path, fake)
    mark_done(store, 0)
    outcome = await run_probe(p02.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    assert outcome is Outcome.CONFIRMED
    assert io.actions == [Action("close_all_companies"), Action("open_company", {"label": "A"})]
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_part2_harness.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.actions'`.

- [x] **Step 3: Write `v2/probes/actions.py`**

```python
"""What a pause or an ask asks for, in machine-readable form (S0-D9, spec §5.8).

A probe passes an Action with every `ctx.pause` / `ctx.ask`. The console shows only the instruction text; the
automated operator (`v2/probes/operator/`) dispatches on `Action.kind` and never parses the English text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PAUSE_KINDS: frozenset[str] = frozenset({
    "tally_running", "restore_seed", "rename_company", "close_all_companies", "open_company",
    "create_voucher", "alter_voucher", "delete_voucher",
    "create_ledger", "alter_ledger", "delete_ledger", "rename_ledger",
    "view_report", "raise_popup", "dismiss_popup", "quit_tally", "backup_company", "restore_company",
})
ASK_KINDS: frozenset[str] = frozenset({
    "wine_version", "data_folder", "tally_version", "edition", "licence", "expense_ledger", "ui_closing_balance",
})


@dataclass(frozen=True)
class Action:
    kind: str
    params: dict[str, Any] = field(default_factory=dict, hash=False)

    def __post_init__(self) -> None:
        if self.kind not in PAUSE_KINDS | ASK_KINDS:
            raise ValueError(f"Unknown action kind: {self.kind!r}")
```

- [x] **Step 4: Update `v2/probes/core.py`** — replace the `Probe` dataclass with:

```python
@dataclass(frozen=True, eq=False)
class Probe:
    id: int
    name: str
    question: str
    feeds: tuple[str, ...]
    parts: dict[str, PartFn]
    requires: tuple[int, ...] = ()
    mutating: bool = False
    guard: bool = True
    educational_sensitive: bool = False
    planned_parts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.planned_parts and not set(self.parts) <= set(self.planned_parts):
            raise ValueError(f"Probe {self.id}: built parts {sorted(self.parts)} must be among {list(self.planned_parts)}")

    @property
    def part_labels(self) -> tuple[str, ...]:
        """Every company part of this probe, built now or in a later plan part (S0 spec §5.1, §5.4 PARTIAL)."""
        return self.planned_parts or tuple(self.parts)
```

- [x] **Step 5: Replace `v2/probes/console.py`**

```python
"""How the runner talks to whoever performs the pauses: a person at the Tally UI, or the automated operator (S0-D9)."""
from __future__ import annotations

from typing import Protocol

from v2.probes.actions import Action


class ProbeIO(Protocol):
    interactive: bool

    def wait(self, instruction: str, action: Action | None = None) -> None: ...

    def ask(self, prompt: str, action: Action | None = None) -> str: ...

    def say(self, message: str) -> None: ...


class ConsoleIO:
    """A person at the Tally UI. The Action is for the automated operator; a person reads the instruction."""

    run_mode = "manual"

    def __init__(self, interactive: bool = True):
        self.interactive = interactive

    def wait(self, instruction: str, action: Action | None = None) -> None:
        input(f"\n>>> {instruction}\n    Press Enter when done... ")

    def ask(self, prompt: str, action: Action | None = None) -> str:
        return input(f"\n>>> {prompt}\n    > ").strip()

    def say(self, message: str) -> None:
        print(message, flush=True)
```

- [x] **Step 6: Update `v2/probes/context.py`**

Add the import below the existing `from v2.probes.capture import Capture` line:
```python
from v2.probes.actions import ASK_KINDS, PAUSE_KINDS, Action
```
Add this property directly after `__init__`:
```python
    @property
    def run_mode(self) -> str:
        """'auto' when the automated operator performs the pauses (S0-D9), else 'manual'."""
        return getattr(self.io, "run_mode", "manual")
```
Replace the methods `pause` and `ask` with:
```python
    def pause(self, instruction: str, action: Action | None = None) -> None:
        if action is not None and action.kind not in PAUSE_KINDS:
            raise ValueError(f"{action.kind!r} is not a pause action")
        if not self.io.interactive:
            raise ProbeBlocked(f"Needs a manual step: {instruction}")
        self.io.wait(instruction, action)
        step: dict[str, Any] = {"n": len(self.manual_steps) + 1, "instruction": instruction, "done_at": _now()}
        if action is not None:
            step["action"] = action.kind
        self.manual_steps.append(step)

    def ask(self, prompt: str, action: Action | None = None) -> str:
        if action is not None and action.kind not in ASK_KINDS:
            raise ValueError(f"{action.kind!r} is not an ask action")
        if not self.io.interactive:
            raise ProbeBlocked(f"Needs a manual step: {prompt}")
        answer = self.io.ask(prompt, action)
        step: dict[str, Any] = {"n": len(self.manual_steps) + 1, "instruction": prompt, "input": answer,
                                "done_at": _now()}
        if action is not None:
            step["action"] = action.kind
        self.manual_steps.append(step)
        return answer
```

- [x] **Step 7: Replace `v2/probes/anchors.py`**

```python
"""Is company A still the seed company's known state? (S0 spec §4.2)

Bills totals come from docs/seed-data-setup.md. The TB rows are compared with the baseline probe 0 captured
right after the restore (tests/fixtures/trial_balance_live.xml is another company and is never used here).
`check_anchors` captures fixtures (probe 0); `check_anchors_direct` doesn't (the anchors steps in ordered runs, §6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from v2.agent.tally.client import TallyClient
from v2.agent.tally.envelopes import build_company_list, wrap_report
from v2.agent.tally.reports import parse_bills, parse_trial_balance
from v2.agent.tally.xml_utils import parse_company_list, sanitize_xml
from v2.probes.context import ProbeContext
from v2.probes.safety import check_company, check_request

SEED_RECEIVABLE = Decimal("970537.00")
SEED_PAYABLE = Decimal("1834142.00")
ANCHOR_FROM = "01-04-2025"
ANCHOR_DATE = "31-03-2026"


@dataclass
class AnchorResult:
    receivable: Decimal | None
    payable: Decimal | None
    tb_rows: dict[str, str]
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def _bills_total(text: str) -> Decimal | None:
    amounts = [bill["amount"] for bill in parse_bills(text)]
    if not amounts or any(amount is None for amount in amounts):
        return None
    return sum(amounts, Decimal("0"))


def _requests(company: str) -> tuple[str, str, str]:
    return (wrap_report("Bills Receivable", ANCHOR_DATE, ANCHOR_DATE, company),
            wrap_report("Bills Payable", ANCHOR_DATE, ANCHOR_DATE, company),
            wrap_report("Trial Balance", ANCHOR_FROM, ANCHOR_DATE, company))


def _evaluate(receivable_text: str, payable_text: str, tb_text: str,
              tb_baseline: dict[str, str] | None) -> AnchorResult:
    receivable = _bills_total(receivable_text)
    payable = _bills_total(payable_text)
    tb_rows = {row["account_name"]: str(row["closing_balance"]) for row in parse_trial_balance(tb_text)}
    result = AnchorResult(receivable=receivable, payable=payable, tb_rows=tb_rows)
    if receivable != SEED_RECEIVABLE:
        result.problems.append(f"Bills Receivable {receivable} ≠ {SEED_RECEIVABLE}")
    if payable != SEED_PAYABLE:
        result.problems.append(f"Bills Payable {payable} ≠ {SEED_PAYABLE}")
    if tb_baseline is not None and tb_rows != tb_baseline:
        result.problems.append("TB group rows differ from probe 0's baseline")
    return result


async def check_anchors(ctx: ProbeContext, step_prefix: str, tb_baseline: dict[str, str] | None) -> AnchorResult:
    receivable_xml, payable_xml, tb_xml = _requests(ctx.company_name)
    receivable_text = await ctx.send(f"{step_prefix}_bills_receivable", receivable_xml)
    payable_text = await ctx.send(f"{step_prefix}_bills_payable", payable_xml)
    tb_text = await ctx.send(f"{step_prefix}_tb", tb_xml)
    return _evaluate(receivable_text, payable_text, tb_text, tb_baseline)


async def _post(client: TallyClient, xml: str) -> str:
    check_request(xml)
    return sanitize_xml((await client.post_xml(xml)).text)


async def check_anchors_direct(client: TallyClient, company: str, tb_baseline: dict[str, str]) -> AnchorResult:
    """The same check, uncaptured, after the company guard (S0 spec §4.2, §6 anchors steps).

    Raises GuardError, TallyConnectionError or TallyResponseError; the runner records them as a failed check.
    """
    check_company(parse_company_list(await _post(client, build_company_list())), company, mutating=False)
    receivable_xml, payable_xml, tb_xml = _requests(company)
    receivable_text = await _post(client, receivable_xml)
    payable_text = await _post(client, payable_xml)
    tb_text = await _post(client, tb_xml)
    return _evaluate(receivable_text, payable_text, tb_text, tb_baseline)
```

- [x] **Step 8: Update `v2/probes/results.py`**

Add `from decimal import Decimal` to the imports, and add these two members to `ResultsStore` (after `record_part`):
```python
    def record_anchor_check(self, *, when: str, label: str, ok: bool, problems: list[str],
                            receivable: Decimal | None, payable: Decimal | None, ran_at: datetime) -> None:
        """One anchors check from an ordered run (S0 spec §4.2), appended to `anchor_checks`."""
        self.data.setdefault("anchor_checks", []).append({
            "when": when, "label": label, "ok": ok, "problems": list(problems),
            "receivable": receivable, "payable": payable, "ran_at": ran_at.isoformat(timespec="seconds"),
        })
        self.save()

    @property
    def anchor_checks(self) -> list[dict[str, Any]]:
        return self.data.get("anchor_checks", [])
```

- [x] **Step 9: Replace `v2/probes/registry.py`**

```python
"""Every S0 probe (built or not), and the run orders from the S0 spec §6 with the §4.2 anchors steps."""
from __future__ import annotations

import importlib
from dataclasses import dataclass

from v2.probes.core import Probe

ANCHORS_BEFORE_PARITY = "anchors:before_parity"
ANCHORS_AFTER_A = "anchors:after_a_batch"
OrderStep = tuple[int | str, str]


@dataclass(frozen=True)
class ProbeInfo:
    id: int
    name: str
    companies: str          # "A", "A+B", "—" for deferred
    tier: str               # "B", "C", "B+C"
    deferred: bool = False
    module: str | None = None


PROBES: tuple[ProbeInfo, ...] = (
    ProbeInfo(0, "environment", "A", "B", module="v2.probes.p00_environment"),
    ProbeInfo(1, "company_counters", "A", "B", module="v2.probes.p01_company_counters"),
    ProbeInfo(2, "active_company_guid", "A", "B", module="v2.probes.p02_active_company_guid"),
    ProbeInfo(3, "voucher_ids_flags", "A+B", "B"),
    ProbeInfo(4, "alterid_filter", "A", "B"),
    ProbeInfo(5, "voucher_month_bounds", "B", "B"),
    ProbeInfo(6, "nested_lines_ledger_guid", "A", "B"),
    ProbeInfo(7, "deleted_vouchers", "A", "B"),
    ProbeInfo(8, "ledger_rename", "A", "B"),
    ProbeInfo(9, "chunk_latency", "—", "C", deferred=True),
    ProbeInfo(10, "error_shapes", "A", "B"),
    ProbeInfo(11, "openings", "B", "B"),
    ProbeInfo(12, "current_snapshots", "A", "B"),
    ProbeInfo(13, "backup_restore", "A", "B"),
    ProbeInfo(14, "special_char_company", "B", "B"),
    ProbeInfo(15, "unicode_compound_units", "B", "B"),
    ProbeInfo(16, "ledger_closing_balance", "A+B", "B"),
    ProbeInfo(17, "ledger_level_tb", "A", "B"),
    ProbeInfo(18, "historical_reports", "A+B", "B"),
    ProbeInfo(19, "counter_stability", "A", "B"),
    ProbeInfo(20, "parity_cost", "—", "C", deferred=True),
    ProbeInfo(21, "full_history_reach", "B", "B+C"),
    ProbeInfo(22, "forex", "B", "B"),
    ProbeInfo(23, "gst_due_dates", "A+B", "B"),
    ProbeInfo(24, "secured_company", "C", "B"),
    ProbeInfo(25, "masters_classification", "A+B", "B"),
)

FIRST_ORDER: list[OrderStep] = [
    (0, "A"), (2, "A"), (1, "A"),
    (ANCHORS_BEFORE_PARITY, "A"), (16, "A"), (17, "A"), (18, "A"), (ANCHORS_AFTER_A, "A"),
    (21, "B"), (16, "B"), (18, "B"),
]

ALL_ORDER: list[OrderStep] = [
    (0, "A"), (2, "A"), (1, "A"),
    (ANCHORS_BEFORE_PARITY, "A"), (16, "A"), (17, "A"), (18, "A"), (19, "A"),
    (3, "A"), (4, "A"), (6, "A"), (12, "A"), (23, "A"), (25, "A"),
    (7, "A"), (8, "A"), (10, "A"), (13, "A"), (ANCHORS_AFTER_A, "A"),
    (21, "B"), (16, "B"), (18, "B"), (5, "B"), (3, "B"), (11, "B"), (14, "B"), (15, "B"), (22, "B"), (23, "B"), (25, "B"),
    (24, "C"),
]


def is_anchor_step(step: int | str) -> bool:
    return isinstance(step, str) and step.startswith("anchors:")


def info(probe_id: int) -> ProbeInfo:
    for item in PROBES:
        if item.id == probe_id:
            return item
    raise KeyError(f"No probe {probe_id}")


def load_probe(probe_id: int) -> Probe | None:
    item = info(probe_id)
    if item.module is None:
        return None
    return importlib.import_module(item.module).PROBE
```

- [x] **Step 10: Replace `v2/probes/runner.py`**

```python
"""Run probe parts: guard → prerequisites → part → record (S0 spec §5.3, §6), plus the anchors steps (§4.2)."""
from __future__ import annotations

from datetime import datetime

from v2.agent.tally.client import TallyClient
from v2.probes.actions import Action
from v2.probes.anchors import check_anchors_direct
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.console import ProbeIO
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.registry import OrderStep, is_anchor_step, load_probe
from v2.probes.results import ResultsStore
from v2.probes.safety import GuardError, check_company, check_mutation_allowed

EDUCATIONAL_SUFFIX = " [Educational mode — confirm on a licensed Tally]"
RESET_HINT = ("Reset it with `uv run --project v2 python -m v2.probes reset-a` (or re-restore the seed backup), "
              "then re-run.")


def _check_requires(probe: Probe, store: ResultsStore) -> None:
    missing = [r for r in probe.requires if store.outcome(r) not in (Outcome.CONFIRMED, Outcome.DIFFERENT)]
    if missing:
        raise ProbeBlocked(f"Run probe(s) {', '.join(map(str, missing))} first.")


def _switch(io: ProbeIO, label: str) -> str | None:
    """Ask for the company switch. Returns why it couldn't be done (the automated operator can fail), else None."""
    instruction = f"Switch Tally to company {label}: {COMPANIES[label]!r} — close every other company."
    if not io.interactive:
        io.say(f"(non-interactive) assuming: {instruction}")
        return None
    try:
        io.wait(instruction, Action("open_company", {"label": label}))
    except ProbeBlocked as exc:
        return f"couldn't switch Tally to company {label}: {exc}"
    return None


async def run_probe(probe: Probe, *, labels: list[str] | None, client: TallyClient, store: ResultsStore,
                    capture: Capture, io: ProbeIO) -> Outcome:
    all_parts = list(probe.part_labels)
    labels = labels or list(probe.parts)
    outcome = store.outcome(probe.id) or Outcome.PARTIAL
    for index, label in enumerate(labels):
        if label not in probe.parts:
            raise ValueError(f"Probe {probe.id} has no part {label!r} (has {', '.join(probe.parts)})")
        switch_error = _switch(io, label) if index > 0 else None
        ctx = ProbeContext(probe=probe, part=label, company_name=COMPANIES[label], client=client,
                           store=store, capture=capture, io=io)
        io.say(f"--- probe {probe.id} ({probe.name}) part {label}: {COMPANIES[label]}")
        interrupted = False
        try:
            if switch_error:
                raise ProbeBlocked(switch_error)
            _check_requires(probe, store)
            if probe.guard:
                check_mutation_allowed(ctx.company_name, mutating=probe.mutating)
                check_company(await ctx.company_names(), ctx.company_name, mutating=probe.mutating)
                if store.confirmed("company_counters"):
                    ctx.company_guid = (await ctx.counters()).get("GUID") or None
            result = await probe.parts[label](ctx)
        except (ProbeBlocked, GuardError) as exc:
            result = PartResult(Outcome.BLOCKED, str(exc))
        except KeyboardInterrupt:
            result = PartResult(Outcome.BLOCKED, "Interrupted by operator (Ctrl-C)")
            interrupted = True
        except Exception as exc:  # noqa: BLE001 - the harness records this instead of crashing (F1)
            result = PartResult(Outcome.BLOCKED, f"Harness error: {type(exc).__name__}: {exc}")

        result.observations = {**ctx.observations, **result.observations}
        if getattr(io, "run_mode", "manual") == "auto":
            result.observations["run_mode"] = "auto"
        if probe.educational_sensitive and store.environment.get("licence") == "educational":
            result.observations["tags"] = ["Educational"]
            result.summary += EDUCATIONAL_SUFFIX
        if result.outcome is Outcome.BLOCKED and ctx.abort_notes:
            result.observations["cleanup_needed"] = list(ctx.abort_notes)

        outcome = store.record_part(probe.id, label, result, all_parts=all_parts, fixtures=ctx.fixtures,
                                    manual_steps=ctx.manual_steps, ran_at=datetime.now().astimezone())
        io.say(f"    part {label}: {result.outcome.value} — {result.summary}")
        if result.outcome is Outcome.BLOCKED and ctx.abort_notes:
            io.say("CLEANUP NEEDED in Tally:")
            for note in ctx.abort_notes:
                io.say(f"  - {note}")
        if interrupted:
            raise KeyboardInterrupt
    return outcome


async def run_anchor_check(step: str, label: str, *, client: TallyClient, store: ResultsStore, io: ProbeIO) -> bool:
    """One anchors check in an ordered run (S0 spec §4.2), recorded in results.json. True if company A is intact."""
    when = step.split(":", 1)[1]
    baseline = store.environment.get("company_a_tb_baseline")
    receivable = payable = None
    if baseline is None:
        problems = ["No TB baseline yet: run probe 0 first."]
    else:
        try:
            result = await check_anchors_direct(client, COMPANIES[label], baseline)
        except Exception as exc:  # noqa: BLE001 - a failed check is recorded, never a crash
            problems = [f"{type(exc).__name__}: {exc}"]
        else:
            problems, receivable, payable = result.problems, result.receivable, result.payable
    store.record_anchor_check(when=when, label=label, ok=not problems, problems=problems, receivable=receivable,
                              payable=payable, ran_at=datetime.now().astimezone())
    io.say(f"--- anchors check ({when}) company {label}: "
           + ("OK" if not problems else "FAILED — " + "; ".join(problems)))
    return not problems


async def run_order(order: list[OrderStep], *, client: TallyClient, store: ResultsStore,
                    capture: Capture, io: ProbeIO, rerun: bool = False) -> None:
    current: str | None = None
    for step, label in order:
        if is_anchor_step(step):
            if label != current:
                error = _switch(io, label)
                if error:
                    io.say(f"Stopped: {error}")
                    return
                current = label
            if not await run_anchor_check(step, label, client=client, store=store, io=io):
                io.say(f"Stopped: company {label} failed the anchors check. {RESET_HINT}")
                return
            continue
        probe = load_probe(step)
        if probe is None:
            io.say(f"--- probe {step}: not built yet, skipped")
            continue
        if label not in probe.parts:
            io.say(f"--- probe {step} part {label}: not built yet, skipped")
            continue
        existing = store.part_outcome(step, label)
        if not rerun and existing in (Outcome.CONFIRMED, Outcome.DIFFERENT):
            io.say(f"--- probe {step} part {label}: already {existing.value}, skipped (use --rerun)")
            continue
        if label != current and probe.guard:
            error = _switch(io, label)
            if error:
                io.say(f"Stopped: {error}")
                return
        current = label
        await run_probe(probe, labels=[label], client=client, store=store, capture=capture, io=io)
        outcome = store.part_outcome(step, label)
        if outcome not in (Outcome.CONFIRMED, Outcome.DIFFERENT):
            io.say(f"Stopped: probe {step} part {label} is {outcome.value}. Fix that, then re-run.")
            return
```

- [x] **Step 11: Replace `v2/probes/report.py`**

```python
"""The readable results doc, generated from results.json only (S0 spec §5.7)."""
from __future__ import annotations

from v2.probes.registry import PROBES
from v2.probes.results import ResultsStore

ANCHOR_ROWS = 5


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def render_report(store: ResultsStore, generated_on: str) -> str:
    env = store.environment
    lines = [
        f"# S0 probe results — {generated_on}",
        "",
        "> Generated by `python -m v2.probes report` from `v2/probes/results/results.json`. Don't edit by hand:",
        "> design consequences go into the Part 1 spec, status into the tracker.",
        "",
        "## Environment",
        "",
        "| Item | Value |",
        "|---|---|",
    ]
    for key in ("wine", "tally_version", "edition", "licence", "run_mode"):
        lines.append(f"| {key} | {_cell(str(env.get(key, '—')))} |")
    lines += ["", "## Results", "", "| Probe | Name | Companies | Outcome | Summary | Design impact |",
              "|---|---|---|---|---|---|"]
    for item in PROBES:
        if item.deferred:
            continue
        entry = store.probe_entry(item.id)
        if entry is None:
            lines.append(f"| {item.id} | {item.name} | {item.companies} | not run | — | — |")
            continue
        parts = sorted(entry["parts"].items())
        summary = "; ".join(f"{label}: {part['summary']}" for label, part in parts)
        impact = "; ".join(f"{label}: {part['spec_impact']}" for label, part in parts if part["spec_impact"])
        remaining = entry.get("remaining") or []
        outcome = f"PARTIAL (remaining: {', '.join(remaining)})" if entry["outcome"] == "PARTIAL" and remaining \
            else entry["outcome"]
        lines.append(f"| {item.id} | {item.name} | {item.companies} | {outcome} | {_cell(summary)} | "
                     f"{_cell(impact) or '—'} |")
    lines += ["", "## Company A anchors checks", ""]
    checks = store.anchor_checks[-ANCHOR_ROWS:]
    if not checks:
        lines.append("No anchors check has run yet.")
    else:
        lines += ["| Ran at | When | Result | Problems |", "|---|---|---|---|"]
        for check in checks:
            problems = _cell("; ".join(check["problems"])) or "—"
            lines.append(f"| {check['ran_at']} | {check['when']} | {'OK' if check['ok'] else 'FAILED'} | {problems} |")
    lines += ["", "## Deferred (tier C, Q29)", ""]
    lines += [f"- Probe {item.id} — {item.name}" for item in PROBES if item.deferred]
    lines.append("- Probe 21's timing half, and the standard-edition runs of probes 7 and 13")
    return "\n".join(lines) + "\n"
```

- [x] **Step 12: Update `v2/tests/probes/fakes.py`**

Add `from v2.probes.actions import Action` to the imports and `RUNNING = b"<RESPONSE>TallyPrime Server is Running</RESPONSE>"`
below `COMPANY_LIST_MARKER`. In `FakeTally.transport().handle`, directly after the `if self.down:` block, add:
```python
            if request.method == "GET":
                return httpx.Response(200, content=RUNNING)
```
Replace the `ScriptedIO` class with:
```python
class ScriptedIO:
    def __init__(self, answers: list[str] | None = None, interactive: bool = True,
                 on_wait: Callable[[str], None] | None = None, on_action: Callable[[Action], None] | None = None,
                 answers_by_kind: dict[str, str] | None = None, run_mode: str = "manual"):
        self.interactive = interactive
        self.run_mode = run_mode
        self.answers = list(answers or [])
        self.answers_by_kind = dict(answers_by_kind or {})
        self.on_wait = on_wait
        self.on_action = on_action
        self.waits: list[str] = []
        self.actions: list[Action | None] = []
        self.asks: list[str] = []
        self.ask_actions: list[Action | None] = []
        self.said: list[str] = []

    def wait(self, instruction: str, action: Action | None = None) -> None:
        self.waits.append(instruction)
        self.actions.append(action)
        if self.on_wait:
            self.on_wait(instruction)
        if self.on_action and action is not None:
            self.on_action(action)

    def ask(self, prompt: str, action: Action | None = None) -> str:
        self.asks.append(prompt)
        self.ask_actions.append(action)
        if action is not None and action.kind in self.answers_by_kind:
            return self.answers_by_kind[action.kind]
        if not self.answers:
            raise AssertionError(f"Unexpected question: {prompt}")
        return self.answers.pop(0)

    def say(self, message: str) -> None:
        self.said.append(message)
```

- [x] **Step 13: Put Actions on probe 0's and probe 2's pauses and asks**

`v2/probes/p00_environment.py` — replace the whole file:
```python
"""Probe 0 — environment check; makes company A (S0 spec §7 "Probe 0"). Every pause / ask carries an Action (S0-D9)."""
from __future__ import annotations

import subprocess

from v2.agent.tally.envelopes import build_company_list, wrap_collection
from v2.agent.tally.xml_utils import read_objects
from v2.probes.actions import Action
from v2.probes.anchors import check_anchors
from v2.probes.companies import COMPANIES, SEED_BACKUP, SEED_COMPANY
from v2.probes.context import POPUP_HINT, ProbeContext
from v2.probes.core import Outcome, PartResult, Probe

GUID_REQUEST = wrap_collection("S0CompanyGuid", "Company", ["Name", "GUID"])
EDITIONS = ("Edit Log", "standard")
LICENCES = ("licensed", "educational")


def wine_version() -> str | None:
    try:
        done = subprocess.run(["wine", "--version"], capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() or None


async def _guid(ctx: ProbeContext, step: str) -> str:
    rows = read_objects(await ctx.send(step, GUID_REQUEST), "COMPANY", ["Name", "GUID"])
    return rows[0]["GUID"] if len(rows) == 1 else ""


def _ask_one_of(ctx: ProbeContext, prompt: str, options: tuple[str, ...], action: Action) -> str:
    """Re-ask `prompt` until the answer matches one of `options` (case-insensitively); returns the canonical spelling."""
    lookup = {option.lower(): option for option in options}
    while True:
        answer = ctx.ask(prompt, action).strip()
        canonical = lookup.get(answer.lower())
        if canonical is not None:
            return canonical
        choices = " or ".join(f"'{option}'" for option in options)
        prompt = f"{answer!r} isn't {choices}. " + prompt


async def run_a(ctx: ProbeContext) -> PartResult:
    ctx.company_name = SEED_COMPANY
    wine = wine_version() or ctx.ask("`wine --version` didn't run here. Type the Wine version:", Action("wine_version"))
    ctx.observe("wine", wine)

    ctx.pause("Start TallyPrime under Wine (README.md 'Installing TallyPrime on macOS') with the XML server on port 9000.",
              Action("tally_running"))
    _, error = await ctx.try_send("company_list", build_company_list())
    if error is not None:
        if error["kind"] == "refused":
            return PartResult(Outcome.FAILED, f"Tally didn't answer on port 9000 ({error['kind']})",
                              spec_impact="S0 can't run under Wine on this Mac; S0 is blocked on Q29 (tier C machine).")
        if error["kind"] == "timeout":
            return PartResult(Outcome.BLOCKED, f"Tally didn't answer on port 9000 ({error['kind']}). {POPUP_HINT}")
        return PartResult(Outcome.BLOCKED, f"Tally didn't answer on port 9000 ({error['kind']})")

    ctx.pause(f"Restore {SEED_BACKUP} into a NEW, separate Tally data folder (not Bharat Traders' usual folder). "
              f"Open only that company and close every other company.", Action("restore_seed"))
    names = await ctx.company_names()
    if names != [SEED_COMPANY]:
        return PartResult(Outcome.BLOCKED, f"Expected only {SEED_COMPANY!r} open after the restore, got {names}")
    guid_before = await _guid(ctx, "guid_before_rename")

    anchors = await check_anchors(ctx, "anchors", tb_baseline=None)
    ctx.observe("anchors", {"receivable": anchors.receivable, "payable": anchors.payable, "tb_rows": anchors.tb_rows})
    if not anchors.ok:
        return PartResult(Outcome.BLOCKED, "Restored company doesn't match the seed figures: "
                          + "; ".join(anchors.problems) + ". Re-restore the seed backup.")

    data_folder = ctx.ask(f"Type the Tally data folder path shown for {SEED_COMPANY!r} (Company Info → this "
                          f"company's Data Path) — it must NOT be Bharat Traders' usual data folder:",
                          Action("data_folder"))
    ctx.observe("data_folder", data_folder)

    ctx.pause(f"In Tally, alter this company (Company menu, Alt+K → Alter) and rename it to {COMPANIES['A']!r}. "
              f"Keep it open.", Action("rename_company", {"from": SEED_COMPANY, "to": COMPANIES["A"]}))
    names = await ctx.company_names()
    if names != [COMPANIES["A"]]:
        return PartResult(Outcome.BLOCKED, f"Expected {COMPANIES['A']!r} after the rename, got {names}")
    ctx.company_name = COMPANIES["A"]
    guid_after = await _guid(ctx, "guid_after_rename")
    ctx.observe("guid_before_rename", guid_before)
    ctx.observe("guid_after_rename", guid_after)
    ctx.observe("guid_changed_on_rename", bool(guid_before) and guid_before != guid_after)
    if not guid_before:
        ctx.observe("guid_note", "GUID not readable via a Company collection; probe 2 decides the read.")

    tally_version = ctx.ask("Tally version (Help → About, e.g. 'TallyPrime 7.0'):", Action("tally_version"))
    edition = _ask_one_of(ctx, "Edition — type 'Edit Log' or 'standard':", EDITIONS, Action("edition"))
    licence = _ask_one_of(ctx, "Licence mode — type 'licensed' or 'educational':", LICENCES, Action("licence"))
    ctx.store.update_environment(wine=wine, tally_version=tally_version, edition=edition, licence=licence,
                                 recorded_by_probe=0)
    ctx.store.update_environment(company_a_tb_baseline=anchors.tb_rows)
    return PartResult(Outcome.CONFIRMED, f"Tally answers under Wine ({wine}); company A made; seed anchors match")


PROBE = Probe(
    id=0,
    name="environment",
    question="Does TallyPrime run under Wine here, and does the seed backup restore into company A with the known figures?",
    feeds=("all probes",),
    parts={"A": run_a},
    guard=False,
)
```

`v2/probes/p02_active_company_guid.py` — add `from v2.probes.actions import Action` to the imports, then change the two
pauses to:
```python
    ctx.pause("Close every company in Tally (keep Tally running): Company menu (Alt+K) → Shut Company, until none is open.",
              Action("close_all_companies"))
```
and
```python
    ctx.pause(f"Open company {ctx.company_name!r} again (only that one).", Action("open_company", {"label": ctx.part}))
```

- [x] **Step 14: Update the registry test** — in `v2/tests/probes/test_cli.py` replace
`test_registry_matches_built_modules` with:

```python
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
```

- [x] **Step 15: Run all v2 tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 17** (the new file: `17 passed`; every part-1 test unchanged and green, including
`test_p00_environment.py`, `test_p02_active_company_guid.py`, `test_runner.py`).

---
### Task 2: Write helpers in `v2/probes/setup/` + a stateful fake Tally

**Files:**
- Modify: `v2/probes/companies.py` (throwaway constants)
- Create: `v2/probes/licence.py`, `v2/probes/setup/__init__.py`, `v2/probes/setup/import_xml.py` (copied),
  `v2/probes/setup/writes.py`
- Create test double: `v2/tests/probes/fake_books.py`
- Modify tests: `v2/tests/test_copied_headers.py`
- Test: `v2/tests/probes/test_setup_writes.py`

**Interfaces:**
- Consumes: `build_company_list`, `wrap_collection`, `wrap_report`, `formula_string` (envelopes), `read_objects`,
  `parse_company_list`, `sanitize_xml` (xml_utils), `safety.check_request`, `COMPANIES`, `SEED_COMPANY`
- Produces:
  - `companies.THROWAWAY_DATE = "20260331"`, `THROWAWAY_DATE_TEXT = "31-Mar-2026"`, `THROWAWAY_EXPENSE_LEDGER = "Electricity"`
  - `licence.LICENCE_REQUEST`, `LicenceInfo(educational: bool | None, release: str)`, `parse_licence_info(text)`
  - `setup.import_xml.esc(s)`, `wrap_import(report_name, company, inner_xml)`, `ImportResult.parse(text)` (+ `.clean`)
  - `setup.writes.TallyWriter(http: httpx.Client, say)` with `post`, `import_`, `company_names`, `voucher`, `ledger`,
    `create_payment(company, *, ledger, amount, narration, cash_ledger="Cash", date=THROWAWAY_DATE, post_dated=False) -> str`,
    `alter_voucher_narration`, `delete_voucher`, `create_ledger`, `alter_ledger_email`, `delete_ledger`, `rename_ledger`,
    `rename_company`, `raise_duplicate_master_popup -> str`, `export_report -> int`, `licence_info -> LicenceInfo`;
    exceptions `WriteRefused`, `WriteFailed`, `WriteTimeout(WriteFailed)`; `check_writable(company)`
  - test double `fake_books`: `FakeBooks(folder=None, *, name=SEED_COMPANY, running=True, loaded=True, educational=True,
    click_polls_on_load=0, busy_polls_on_load=0)` with `.transport()`, `.state`, `.start(load)`, `.stop()`,
    `.companies()`, `.requests`, `.popup`; `seed_state(name)`, `write_company_folder(folder, name)`,
    `import_result(...)`, `sync_client(transport)`, `STATE_FILE`, `GUID`

- [x] **Step 1: Add the throwaway constants to `v2/probes/companies.py`** (append):

```python
# Throwaway objects on company A (S0 spec §4.2, §5.8). Educational mode accepts voucher dates on the 1st, 2nd or 31st
# of a month only (live 2026-09-22), so every throwaway voucher is dated 31-Mar-2026, inside A's books period.
THROWAWAY_DATE = "20260331"
THROWAWAY_DATE_TEXT = "31-Mar-2026"
THROWAWAY_EXPENSE_LEDGER = "Electricity"   # company A has no "Bank Charges"; this is its first Indirect Expenses ledger
```

- [x] **Step 2: Write the test double** — `v2/tests/probes/fake_books.py`

```python
"""A stateful fake TallyPrime for the operator and write-helper tests: one company, imports change it.

With a folder the company data lives in `<folder>/fake_company.json`, so file-copy backup / restore / reset behave
the way they do on the real s0probe folder. Nothing here touches Wine or the real Tally.
"""
from __future__ import annotations

import copy
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

from v2.probes.companies import SEED_COMPANY
from v2.tests.probes.fakes import company_list_xml, objects_xml

GUID = "710de34a-3661-4a7b-8148-c2206c3b3e17"
STATE_FILE = "fake_company.json"
COMPANY_LIST_MARKER = "<ID>List of Companies</ID>"


def seed_state(name: str = SEED_COMPANY) -> dict:
    return {
        "name": name, "guid": GUID, "alt_vch": 50, "alt_mst": 266, "last_voucher_date": "20260301",
        "next_master_id": 51,
        "ledgers": {
            "Cash": {"parent": "Cash-in-Hand", "email": "", "alter_id": 10, "guid": f"{GUID}-0000000a"},
            "Electricity": {"parent": "Indirect Expenses", "email": "", "alter_id": 243, "guid": f"{GUID}-000000f1"},
            "Rajesh Computers": {"parent": "South Zone Debtors", "email": "", "alter_id": 30, "guid": f"{GUID}-0000001e"},
        },
        "stock_groups": ["Electronics"],
        "vouchers": {},
    }


def write_company_folder(folder: Path, name: str = SEED_COMPANY) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / STATE_FILE).write_text(json.dumps(seed_state(name)), encoding="utf-8")


def import_result(created: int = 0, altered: int = 0, deleted: int = 0, errors: int = 0, last_vch_id: str = "0",
                  line_error: str = "") -> str:
    """The IMPORTRESULT shape TallyPrime 7 answers an import with (live 2026-09-22)."""
    err = f"<LINEERROR>{line_error}</LINEERROR>" if line_error else ""
    return ("<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER><BODY><DATA><IMPORTRESULT>"
            f"<CREATED>{created}</CREATED><ALTERED>{altered}</ALTERED><DELETED>{deleted}</DELETED>"
            f"<LASTVCHID>{last_vch_id}</LASTVCHID><LASTMID>0</LASTMID><COMBINED>0</COMBINED><IGNORED>0</IGNORED>"
            f"<ERRORS>{errors}</ERRORS><CANCELLED>0</CANCELLED><EXCEPTIONS>0</EXCEPTIONS>{err}"
            "</IMPORTRESULT></DATA></BODY></ENVELOPE>")


def sync_client(transport: httpx.BaseTransport) -> httpx.Client:
    return httpx.Client(base_url="http://localhost:9000", transport=transport, trust_env=False)


class FakeBooks:
    """Tally running or not, a loaded company, a licence box (`click_polls`), a busy load (`busy_polls`), a modal."""

    def __init__(self, folder: Path | None = None, *, name: str = SEED_COMPANY, running: bool = True,
                 loaded: bool = True, educational: bool = True, click_polls_on_load: int = 0,
                 busy_polls_on_load: int = 0):
        self.folder = folder
        self._memory = seed_state(name)
        self.running = running
        self.loaded = loaded
        self.educational = educational
        self.click_polls_on_load = click_polls_on_load
        self.busy_polls_on_load = busy_polls_on_load
        self.click_polls = 0
        self.busy_polls = 0
        self.popup = False
        self.requests: list[str] = []

    # --- company data ---------------------------------------------------------------------------------------------
    @property
    def state(self) -> dict:
        if self.folder is None:
            return copy.deepcopy(self._memory)
        return json.loads((self.folder / STATE_FILE).read_text(encoding="utf-8"))

    def _save(self, state: dict) -> None:
        if self.folder is None:
            self._memory = state
        else:
            (self.folder / STATE_FILE).write_text(json.dumps(state), encoding="utf-8")

    # --- process lifecycle (driven by FakeRunner) ---------------------------------------------------------------------
    def start(self, load: bool) -> None:
        self.running, self.loaded, self.popup = True, load, False
        self.click_polls = self.click_polls_on_load if load else 0
        self.busy_polls = self.busy_polls_on_load if load else 0

    def stop(self) -> None:
        self.running = self.loaded = self.popup = False

    def companies(self) -> list[str]:
        """What a company-list request sees; while the licence box is up the list is empty."""
        if not self.loaded:
            return []
        if self.click_polls > 0:
            self.click_polls -= 1
            return []
        return [self.state["name"]]

    # --- the XML server -------------------------------------------------------------------------------------------
    def transport(self) -> httpx.MockTransport:
        def handle(request: httpx.Request) -> httpx.Response:
            body = request.content.decode("utf-8")
            self.requests.append(body)
            if not self.running:
                raise httpx.ConnectError("connection refused", request=request)
            if self.popup:
                raise httpx.ReadTimeout("a modal is open", request=request)
            if request.method == "GET":
                return httpx.Response(200, content=b"<RESPONSE>TallyPrime Server is Running</RESPONSE>")
            if self.busy_polls > 0 and COMPANY_LIST_MARKER in body:
                self.busy_polls -= 1
                raise httpx.ReadTimeout("loading the company", request=request)
            return httpx.Response(200, content=self._answer(body, request).encode("utf-8"))

        return httpx.MockTransport(handle)

    def _answer(self, body: str, request: httpx.Request) -> str:
        if "<TYPE>Function</TYPE>" in body:
            return ("<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>1</STATUS><PRODMAJORREL>7</PRODMAJORREL>"
                    f"<PRODMINORREL>0</PRODMINORREL></HEADER><BODY><DATA><RESULT>{'Yes' if self.educational else 'No'}"
                    "</RESULT></DATA></BODY></ENVELOPE>")
        if COMPANY_LIST_MARKER in body:
            return company_list_xml(self.companies())
        if not self.loaded or self.click_polls > 0:
            return "<ENVELOPE></ENVELOPE>"
        if "<TALLYREQUEST>Import Data</TALLYREQUEST>" in body:
            return self._import(body, request)
        state = self.state
        if "S0CompanyCounters" in body:
            return objects_xml("COMPANY", [{
                "Name": state["name"], "GUID": state["guid"], "AltVchId": str(state["alt_vch"]),
                "AltMstId": str(state["alt_mst"]), "BooksFrom": "20250401",
                "LastVoucherDate": state["last_voucher_date"], "AlterID": str(state["alt_mst"])}])
        if "S0OpVouchers" in body:
            return objects_xml("VOUCHER", [{"MasterId": mid, "Narration": v["narration"], "Date": v["date"],
                                            "IsPostDated": v["post_dated"]} for mid, v in state["vouchers"].items()])
        if "S0LedgerList" in body:
            return objects_xml("LEDGER", [{"Name": n, "Parent": led["parent"]} for n, led in state["ledgers"].items()])
        if "S0OpLedger" in body or "S0OneLedger" in body:
            match = re.search(r'\$Name = "([^"]*)"', body)
            wanted = html.unescape(match.group(1)) if match else ""
            led = state["ledgers"].get(wanted)
            rows = [] if led is None else [{"Name": wanted, "Parent": led["parent"], "Email": led["email"],
                                            "GUID": led["guid"], "AlterID": str(led["alter_id"])}]
            return objects_xml("LEDGER", rows)
        return "<ENVELOPE></ENVELOPE>"

    def _import(self, body: str, request: httpx.Request) -> str:
        state = self.state
        element = next(iter(ET.fromstring(body).find(".//TALLYMESSAGE")))
        action = element.get("ACTION", "")
        if element.tag == "COMPANY":
            new_name = element.findtext("NAME")      # the NAME.LIST variant answers ALTERED=1 and changes nothing
            if new_name and element.get("NAME") == state["name"]:
                state["name"] = new_name
                self._save(state)
            return import_result(altered=1)
        if element.tag == "STOCKGROUP" and action == "Create":
            if element.get("NAME") in state["stock_groups"]:
                self.popup = True                    # LESSONS §15 rule 10: a duplicate create raises a blocking modal
                raise httpx.ReadTimeout("duplicate master modal", request=request)
            state["stock_groups"].append(element.get("NAME"))
            state["alt_mst"] += 1
            self._save(state)
            return import_result(created=1)
        if element.tag == "LEDGER":
            return self._ledger(state, element, action, request)
        if element.tag == "VOUCHER":
            return self._voucher(state, element, action)
        return import_result(errors=1, line_error=f"fake: unsupported {element.tag}")

    def _ledger(self, state: dict, element: ET.Element, action: str, request: httpx.Request) -> str:
        name = element.get("NAME", "")
        ledgers = state["ledgers"]
        if action == "Create":
            if name in ledgers:
                self.popup = True
                raise httpx.ReadTimeout("duplicate master modal", request=request)
            state["alt_mst"] += 1
            ledgers[name] = {"parent": element.findtext("PARENT", ""), "email": "", "alter_id": state["alt_mst"],
                             "guid": f"{state['guid']}-{state['alt_mst']:08x}"}
            self._save(state)
            return import_result(created=1)
        if name not in ledgers:
            return import_result(errors=1, line_error=f"Could not find Ledger '{name}'")
        if action == "Delete":
            del ledgers[name]
            state["alt_mst"] += 1
            self._save(state)
            return import_result(deleted=1)
        changed = False
        new_name = element.findtext("NAME.LIST/NAME")
        if new_name and new_name != name:
            ledgers[new_name] = ledgers.pop(name)
            name, changed = new_name, True
        email = element.findtext("EMAIL")
        if email:                                     # an empty value is silently ignored (live 2026-09-22)
            ledgers[name]["email"] = email
            changed = True
        if changed:
            state["alt_mst"] += 1
            ledgers[name]["alter_id"] = state["alt_mst"]
        self._save(state)
        return import_result(altered=1)

    def _voucher(self, state: dict, element: ET.Element, action: str) -> str:
        vouchers = state["vouchers"]
        if action == "Create":
            mid = str(state["next_master_id"])
            state["next_master_id"] += 1
            date = element.findtext("DATE", "")
            vouchers[mid] = {"narration": element.findtext("NARRATION", ""), "date": date,
                             "post_dated": element.findtext("ISPOSTDATED") or "No"}
            state["alt_vch"] += 1
            state["last_voucher_date"] = max(state["last_voucher_date"], date)
            self._save(state)
            return import_result(created=1, last_vch_id=mid)
        mid = element.get("TAGVALUE", "")
        if mid not in vouchers:
            return import_result(errors=1, line_error="Voucher not found")
        if action == "Alter":
            narration = element.findtext("NARRATION")
            if narration:
                vouchers[mid]["narration"] = narration
            state["alt_vch"] += 1
            self._save(state)
            return import_result(altered=1, last_vch_id=mid)
        if action == "Delete":
            del vouchers[mid]
            state["alt_vch"] += 3                     # live: a delete moved AltVchId by 3
            self._save(state)
            return import_result(deleted=1, last_vch_id=mid)
        return import_result(errors=1, line_error=f"fake: unsupported voucher action {action}")
```

- [x] **Step 3: Write the failing tests** — `v2/tests/probes/test_setup_writes.py`

```python
import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.setup.import_xml import ImportResult, wrap_import
from v2.probes.setup.writes import TallyWriter, WriteFailed, WriteRefused
from v2.tests.probes.fake_books import FakeBooks, import_result, sync_client
from v2.tests.probes.fakes import FakeTally, objects_xml

A = COMPANIES["A"]


def _writer(books):
    said: list[str] = []
    return TallyWriter(sync_client(books.transport()), said.append), said


def _imports(books):
    return [r for r in books.requests if "<TALLYREQUEST>Import Data</TALLYREQUEST>" in r]


def test_import_result_parses_the_live_response_shape():
    result = ImportResult.parse(import_result(created=1, last_vch_id="51"))
    assert (result.created, result.altered, result.deleted, result.errors, result.last_vch_id) == (1, 0, 0, 0, "51")
    assert result.clean
    assert not ImportResult.parse(import_result(errors=1, line_error="Voucher not found")).clean


def test_copied_import_envelope_escapes_and_checks_the_report():
    root = ET.fromstring(wrap_import("All Masters", "Sharma & Sons' Probe Traders", "<LEDGER/>"))
    assert root.find(".//SVCURRENTCOMPANY").text == "Sharma & Sons' Probe Traders"
    with pytest.raises(ValueError):
        wrap_import("Everything", A, "<LEDGER/>")


def test_payment_create_alter_delete_round_trip():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    master_id = writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-throwaway 1")
    assert master_id == "51" and books.state["alt_vch"] == 51
    writer.alter_voucher_narration(A, master_id, "S0-throwaway 1 (altered)")
    assert books.state["vouchers"]["51"]["narration"] == "S0-throwaway 1 (altered)"
    writer.delete_voucher(A, master_id)
    assert books.state["vouchers"] == {} and books.state["alt_vch"] == 55


def test_payment_uses_the_verified_voucher_shape():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    writer.delete_voucher(A, writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-t"))
    create, delete = _imports(books)
    for fragment in ("<ALLLEDGERENTRIES.LIST>", "<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>",
                     "<DATE>20260331</DATE>", "<AMOUNT>-1.00</AMOUNT>", "<AMOUNT>1.00</AMOUNT>",
                     "<LEDGERNAME>Cash</LEDGERNAME>", "<REPORTNAME>Vouchers</REPORTNAME>"):
        assert fragment in create
    assert 'DATE="31-Mar-2026"' in delete and 'TAGNAME="Master ID" TAGVALUE="51"' in delete


def test_post_dated_payment_sends_the_flag_and_logs_the_read_back():
    books = FakeBooks(name=A)
    writer, said = _writer(books)
    writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-pd", post_dated=True)
    assert "<ISPOSTDATED>Yes</ISPOSTDATED>" in _imports(books)[0]
    assert books.state["vouchers"]["51"]["post_dated"] == "Yes"
    assert any("read-back IsPostDated" in line for line in said)


def test_writes_to_a_company_without_probe_are_refused_before_sending():
    books = FakeBooks(name="Bharat Traders Private Limited")
    writer, _ = _writer(books)
    before = len(books.requests)
    with pytest.raises(WriteRefused):
        writer.create_payment("Bharat Traders Private Limited", ledger="Electricity", amount=Decimal("1"),
                              narration="S0-x")
    with pytest.raises(WriteRefused):
        writer.delete_ledger("Bharat Traders Private Limited", "Cash")
    assert len(books.requests) == before


def test_seed_rename_is_the_only_exception():
    books = FakeBooks(name=SEED_COMPANY)
    writer, _ = _writer(books)
    with pytest.raises(WriteRefused):
        writer.rename_company(SEED_COMPANY, "Bharat Traders Copy")
    writer.rename_company(SEED_COMPANY, A)
    assert books.companies() == [A]
    assert "<COMPANY NAME=\"Bharat Traders Private Limited\" ACTION=\"Alter\"><NAME>" in _imports(books)[0]


def test_an_empty_value_alter_is_refused():
    writer, _ = _writer(FakeBooks(name=A))
    with pytest.raises(ValueError):
        writer.alter_ledger_email(A, "Electricity", "")


def test_ledger_create_alter_delete_and_rename():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    writer.create_ledger(A, "S0 Probe Ledger", "Indirect Expenses")
    writer.alter_ledger_email(A, "S0 Probe Ledger", "s0probe-1@example.com")
    assert books.state["ledgers"]["S0 Probe Ledger"]["email"] == "s0probe-1@example.com"
    writer.delete_ledger(A, "S0 Probe Ledger")
    assert "S0 Probe Ledger" not in books.state["ledgers"]
    writer.rename_ledger(A, "Rajesh Computers", "Rajesh Computers S0")
    writer.rename_ledger(A, "Rajesh Computers S0", "Rajesh Computers")
    assert "Rajesh Computers" in books.state["ledgers"]
    assert books.state["alt_mst"] == 266 + 5


def test_duplicate_ledger_create_is_refused_before_sending():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    with pytest.raises(WriteFailed, match="already exists"):
        writer.create_ledger(A, "Electricity", "Indirect Expenses")
    assert _imports(books) == []
    assert not books.popup


def test_altered_1_without_the_change_fails_the_write():
    fake = FakeTally([A])
    fake.route("<TALLYREQUEST>Import Data</TALLYREQUEST>", lambda body: import_result(altered=1))
    fake.route("S0OpLedger", lambda body: objects_xml("LEDGER", [
        {"Name": "S0 Probe Ledger", "Parent": "Indirect Expenses", "Email": "", "AlterID": "1"}]))
    writer = TallyWriter(sync_client(fake.transport()), lambda line: None)
    with pytest.raises(WriteFailed, match="not proof"):
        writer.alter_ledger_email(A, "S0 Probe Ledger", "s0probe-1@example.com")


def test_duplicate_stock_group_raises_the_popup():
    books = FakeBooks(name=A)
    writer, _ = _writer(books)
    assert writer.raise_duplicate_master_popup(A) == "timeout"
    assert books.popup
    with pytest.raises(WriteFailed):
        writer.company_names()


def test_licence_info_reads_mode_and_release():
    writer, _ = _writer(FakeBooks(name=A))
    info = writer.licence_info()
    assert info.educational is True and info.release == "7.0"
    assert _writer(FakeBooks(name=A, educational=False))[0].licence_info().educational is False
```

- [x] **Step 4: Add the copied file to the header test** — in `v2/tests/test_copied_headers.py` add to `COPIED`:

```python
    "probes/setup/import_xml.py": "backend/tally_bridge/import_builder.py",
```

- [x] **Step 5: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_setup_writes.py v2/tests/test_copied_headers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.setup'` (and the new header case fails with
`FileNotFoundError`).

- [x] **Step 6: Write `v2/probes/licence.py`**

```python
"""TallyPrime's licence mode and release, read with a TYPE=Function export.

Live 2026-09-22: `$$LicenseInfo` with the parameter `IsEducationalMode` answered <RESULT>Yes</RESULT>, and the XML
header carried PRODMAJORREL 7 / PRODMINORREL 0. Used by the automated operator's answers and by probe 10.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

LICENCE_REQUEST = """<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Function</TYPE>
<ID>$$LicenseInfo</ID>
</HEADER>
<BODY>
<DESC>
<FUNCPARAMLIST>
<PARAM>IsEducationalMode</PARAM>
</FUNCPARAMLIST>
</DESC>
</BODY>
</ENVELOPE>"""


@dataclass(frozen=True)
class LicenceInfo:
    educational: bool | None     # None when the answer holds no Yes / No
    release: str                 # e.g. "7.0"; "" when the header doesn't carry it


def parse_licence_info(text: str) -> LicenceInfo:
    result = re.search(r"<RESULT[^>]*>\s*([^<]*?)\s*</RESULT>", text)
    major = re.search(r"<PRODMAJORREL[^>]*>\s*(\d+)\s*</PRODMAJORREL>", text)
    minor = re.search(r"<PRODMINORREL[^>]*>\s*(\d+)\s*</PRODMINORREL>", text)
    value = result.group(1).strip().lower() if result else ""
    educational = True if value == "yes" else False if value == "no" else None
    release = f"{major.group(1)}.{minor.group(1) if minor else '0'}" if major else ""
    return LicenceInfo(educational=educational, release=release)
```

- [x] **Step 7: Write `v2/probes/setup/__init__.py`**

```python
"""Tally write code for S0 only (S0-D8): the copied import envelope and the automated operator's write helpers.
Probe modules never import this package; v2/agent/ never imports v2.probes at all."""
```

- [x] **Step 8: Write `v2/probes/setup/import_xml.py`** (copied)

```python
# Copied from: backend/tally_bridge/import_builder.py @ c04d7d2
# Changes: only _esc (now esc) and _wrap_import (now wrap_import) are copied, no voucher/master builders; the report
# name is checked at run time instead of by Literal; ImportResult (the parsed CREATED/ALTERED/… counts) is new.
"""The Tally XML import envelope. Used only by v2/probes/setup/ (the agent ships with no write code, S0-D8)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from xml.sax.saxutils import escape as xml_escape

REPORTS = ("Vouchers", "All Masters")


def esc(s: str) -> str:
    """Escape XML special characters in element text and attribute values."""
    return xml_escape(s, {'"': "&quot;", "'": "&apos;"})


def wrap_import(report_name: str, company: str, inner_xml: str) -> str:
    """Wrap entity XML in the standard IMPORTDATA envelope."""
    if report_name not in REPORTS:
        raise ValueError(f"Unknown import report {report_name!r} (expected one of {REPORTS})")
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>{report_name}</REPORTNAME>
<STATICVARIABLES><SVCURRENTCOMPANY>{esc(company)}</SVCURRENTCOMPANY></STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
{inner_xml}
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA></BODY></ENVELOPE>"""


def _count(text: str, tag: str) -> int:
    match = re.search(rf"<{tag}>\s*(-?\d+)\s*</{tag}>", text)
    return int(match.group(1)) if match else 0


@dataclass(frozen=True)
class ImportResult:
    created: int
    altered: int
    deleted: int
    errors: int
    exceptions: int
    last_vch_id: str
    line_error: str

    @classmethod
    def parse(cls, text: str) -> "ImportResult":
        vch = re.search(r"<LASTVCHID>\s*([^<]*?)\s*</LASTVCHID>", text)
        line_error = re.search(r"<LINEERROR>([^<]*)</LINEERROR>", text)
        return cls(created=_count(text, "CREATED"), altered=_count(text, "ALTERED"), deleted=_count(text, "DELETED"),
                   errors=_count(text, "ERRORS"), exceptions=_count(text, "EXCEPTIONS"),
                   last_vch_id=vch.group(1) if vch else "",
                   line_error=line_error.group(1).strip() if line_error else "")

    @property
    def clean(self) -> bool:
        return self.errors == 0 and self.exceptions == 0 and not self.line_error
```

- [x] **Step 9: Write `v2/probes/setup/writes.py`**

```python
"""Write helpers for the automated operator (S0-D9, spec §5.8). Verified shapes only:

- Payment via ALLLEDGERENTRIES.LIST + Accounting Voucher View (docs/tally-write-exploration-v4.md Op 8; live 2026-09-22)
- header-field alter and delete by Master ID, DATE="DD-MMM-YYYY" (v4 "Voucher delete"; live 2026-09-22)
- ledger create / delete with NAME.LIST, rename with NAME.LIST (v4 "Ledger delete", "permanent lock"), EMAIL alter
- company rename with a <NAME> child (live 2026-09-22 — the NAME.LIST variant does nothing)

Every write is read back (LESSONS §12). Writes go only to companies with "Probe" in the name; the one exception is
renaming the fresh seed copy to company A, which the operator does only on its own s0probe Tally.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Callable

import httpx

from v2.agent.tally.envelopes import build_company_list, formula_string, wrap_collection, wrap_report
from v2.agent.tally.xml_utils import parse_company_list, read_objects, sanitize_xml
from v2.probes.companies import COMPANIES, SEED_COMPANY, THROWAWAY_DATE, THROWAWAY_DATE_TEXT
from v2.probes.licence import LICENCE_REQUEST, LicenceInfo, parse_licence_info
from v2.probes.safety import check_request
from v2.probes.setup.import_xml import ImportResult, esc, wrap_import

READBACK_FROM, READBACK_TO = "01-04-2025", "31-03-2026"
POPUP_STOCK_GROUP = "Electronics"    # exists in the seed company; a duplicate create raises the blocking modal
VOUCHER_FIELDS = ["MasterId", "Narration", "Date", "IsPostDated"]
LEDGER_FIELDS = ["Name", "Parent", "Email", "AlterID"]


class WriteRefused(Exception):
    """The mutation guard refused; nothing was sent."""


class WriteFailed(Exception):
    """Tally didn't confirm the write, or the read-back didn't show it."""


class WriteTimeout(WriteFailed):
    """Tally didn't answer in time (a modal may be open)."""


def check_writable(company: str) -> None:
    if "Probe" not in company:
        raise WriteRefused(f"Refusing to write to {company!r}: only companies with 'Probe' in the name.")


class TallyWriter:
    def __init__(self, http: httpx.Client, say: Callable[[str], None]):
        self.http = http
        self.say = say

    # --- transport --------------------------------------------------------------------------------------------------
    def post(self, xml: str, timeout: float = 30.0) -> str:
        check_request(xml)
        try:
            response = self.http.post("/", content=xml.encode("utf-8"),
                                      headers={"Content-Type": "text/xml; charset=utf-8"},
                                      timeout=httpx.Timeout(timeout, connect=5.0))
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise WriteTimeout(f"Tally didn't answer within {timeout:.0f}s ({type(exc).__name__})") from exc
        except httpx.HTTPError as exc:
            raise WriteFailed(f"Tally request failed: {type(exc).__name__}: {exc}") from exc
        return sanitize_xml(response.text)

    def import_(self, report: str, company: str, inner: str, timeout: float = 30.0) -> ImportResult:
        result = ImportResult.parse(self.post(wrap_import(report, company, inner), timeout))
        self.say(f"import ({report}) → created={result.created} altered={result.altered} deleted={result.deleted} "
                 f"errors={result.errors} exceptions={result.exceptions} lastvchid={result.last_vch_id!r}"
                 + (f" lineerror={result.line_error!r}" if result.line_error else ""))
        return result

    # --- read-backs (uncaptured; probes make their own captured reads) -----------------------------------------------
    def company_names(self) -> list[str]:
        return parse_company_list(self.post(build_company_list(), timeout=10.0))

    def voucher(self, company: str, master_id: str) -> dict[str, str] | None:
        xml = wrap_collection("S0OpVouchers", "Voucher", VOUCHER_FIELDS, company,
                              static_vars={"SVFROMDATE": READBACK_FROM, "SVTODATE": READBACK_TO},
                              extra_collection_xml="<CHILDOF>$$VchTypeAllVouchers</CHILDOF>")
        for row in read_objects(self.post(xml), "VOUCHER", VOUCHER_FIELDS):
            if row["MasterId"] == master_id:
                return row
        return None

    def ledger(self, company: str, name: str) -> dict[str, str] | None:
        xml = wrap_collection("S0OpLedger", "Ledger", LEDGER_FIELDS, company,
                              filters=[("S0OpOnly", f"$Name = {formula_string(name)}")])
        rows = [r for r in read_objects(self.post(xml), "LEDGER", LEDGER_FIELDS) if r["Name"] == name]
        return rows[0] if rows else None

    # --- vouchers ---------------------------------------------------------------------------------------------------
    def create_payment(self, company: str, *, ledger: str, amount: Decimal, narration: str,
                       cash_ledger: str = "Cash", date: str = THROWAWAY_DATE, post_dated: bool = False) -> str:
        """Cash → `ledger` Payment; returns its Master ID (LASTVCHID)."""
        check_writable(company)
        if amount <= 0:
            raise ValueError("The payment amount must be positive")
        value = f"{amount:.2f}"
        flag = "\n  <ISPOSTDATED>Yes</ISPOSTDATED>" if post_dated else ""
        inner = f"""<VOUCHER VCHTYPE="Payment" ACTION="Create">
  <DATE>{date}</DATE>
  <NARRATION>{esc(narration)}</NARRATION>
  <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
  <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>{flag}
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>{esc(ledger)}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
    <AMOUNT>-{value}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST>
    <LEDGERNAME>{esc(cash_ledger)}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
    <AMOUNT>{value}</AMOUNT>
  </ALLLEDGERENTRIES.LIST>
</VOUCHER>"""
        result = self.import_("Vouchers", company, inner)
        if result.created != 1 or not result.clean or result.last_vch_id in ("", "0"):
            raise WriteFailed(f"Voucher {narration!r} not created: {result}")
        row = self.voucher(company, result.last_vch_id)
        if row is None or row["Narration"] != narration:
            raise WriteFailed(f"Voucher {narration!r} (Master ID {result.last_vch_id}) not found on read-back")
        if post_dated:
            self.say(f"read-back IsPostDated for Master ID {result.last_vch_id}: {row['IsPostDated']!r}")
        return result.last_vch_id

    def alter_voucher_narration(self, company: str, master_id: str, narration: str, *, vch_type: str = "Payment",
                                date_text: str = THROWAWAY_DATE_TEXT) -> None:
        check_writable(company)
        inner = (f'<VOUCHER DATE="{date_text}" TAGNAME="Master ID" TAGVALUE="{esc(master_id)}" '
                 f'VCHTYPE="{esc(vch_type)}" ACTION="Alter">\n<NARRATION>{esc(narration)}</NARRATION>\n</VOUCHER>')
        result = self.import_("Vouchers", company, inner)
        if result.altered != 1 or result.created != 0 or not result.clean:
            raise WriteFailed(f"Voucher {master_id} not altered (or duplicated): {result}")
        row = self.voucher(company, master_id)
        if row is None or row["Narration"] != narration:
            raise WriteFailed(f"Voucher {master_id}: narration unchanged on read-back (altered=1 is not proof, LESSONS §12)")

    def delete_voucher(self, company: str, master_id: str, *, vch_type: str = "Payment",
                       date_text: str = THROWAWAY_DATE_TEXT) -> None:
        check_writable(company)
        inner = (f'<VOUCHER DATE="{date_text}" VCHTYPE="{esc(vch_type)}" TAGNAME="Master ID" '
                 f'TAGVALUE="{esc(master_id)}" ACTION="Delete"></VOUCHER>')
        result = self.import_("Vouchers", company, inner)
        if result.deleted != 1 or not result.clean:
            raise WriteFailed(f"Voucher {master_id} not deleted: {result}")
        if self.voucher(company, master_id) is not None:
            raise WriteFailed(f"Voucher {master_id} still there after the delete")

    # --- ledgers ----------------------------------------------------------------------------------------------------
    def create_ledger(self, company: str, name: str, parent: str) -> None:
        check_writable(company)
        if self.ledger(company, name) is not None:
            raise WriteFailed(f"Ledger {name!r} already exists — a duplicate create freezes Tally (LESSONS §15 rule 10)")
        inner = (f'<LEDGER NAME="{esc(name)}" ACTION="Create">\n  <NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST>\n'
                 f'  <PARENT>{esc(parent)}</PARENT>\n  <ISBILLWISEON>No</ISBILLWISEON>\n</LEDGER>')
        result = self.import_("All Masters", company, inner)
        if result.created != 1 or not result.clean:
            raise WriteFailed(f"Ledger {name!r} not created: {result}")
        row = self.ledger(company, name)
        if row is None or row["Parent"] != parent:
            raise WriteFailed(f"Ledger {name!r} not found under {parent!r} on read-back")

    def alter_ledger_email(self, company: str, name: str, email: str) -> None:
        check_writable(company)
        if not email:
            raise ValueError("An empty-value alter is silently ignored by Tally (live 2026-09-22); never 'clear' a field")
        inner = f'<LEDGER NAME="{esc(name)}" ACTION="Alter">\n<EMAIL>{esc(email)}</EMAIL>\n</LEDGER>'
        result = self.import_("All Masters", company, inner)
        if result.altered != 1 or not result.clean:
            raise WriteFailed(f"Ledger {name!r} not altered: {result}")
        row = self.ledger(company, name)
        if row is None or row["Email"] != email:
            raise WriteFailed(f"Ledger {name!r}: EMAIL unchanged on read-back (altered=1 is not proof, LESSONS §12)")

    def delete_ledger(self, company: str, name: str) -> None:
        check_writable(company)
        inner = f'<LEDGER NAME="{esc(name)}" ACTION="Delete">\n<NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST>\n</LEDGER>'
        result = self.import_("All Masters", company, inner)
        if result.deleted != 1 or not result.clean:
            raise WriteFailed(f"Ledger {name!r} not deleted: {result}")
        if self.ledger(company, name) is not None:
            raise WriteFailed(f"Ledger {name!r} still there after the delete")

    def rename_ledger(self, company: str, old: str, new: str) -> None:
        check_writable(company)
        if self.ledger(company, new) is not None:
            raise WriteFailed(f"A ledger {new!r} already exists")
        inner = f'<LEDGER NAME="{esc(old)}" ACTION="Alter">\n<NAME.LIST><NAME>{esc(new)}</NAME></NAME.LIST>\n</LEDGER>'
        result = self.import_("All Masters", company, inner)
        if result.altered != 1 or not result.clean:
            raise WriteFailed(f"Ledger {old!r} not renamed: {result}")
        if self.ledger(company, new) is None or self.ledger(company, old) is not None:
            raise WriteFailed(f"Ledger rename {old!r} → {new!r} not visible on read-back")

    # --- company ----------------------------------------------------------------------------------------------------
    def rename_company(self, old: str, new: str) -> None:
        if not (old == SEED_COMPANY and new == COMPANIES["A"]):
            check_writable(old)
            check_writable(new)
        inner = f'<COMPANY NAME="{esc(old)}" ACTION="Alter"><NAME>{esc(new)}</NAME></COMPANY>'
        result = self.import_("All Masters", old, inner)
        if not result.clean:
            raise WriteFailed(f"Company rename refused: {result}")
        names = self.company_names()
        if names != [new]:
            raise WriteFailed(f"Company rename didn't take effect: Tally shows {names}")

    # --- popup, report view, licence ---------------------------------------------------------------------------------
    def raise_duplicate_master_popup(self, company: str, timeout: float = 10.0) -> str:
        """LESSONS §15 rule 10: a CREATE of an existing stock group raises a blocking modal. Returns what happened."""
        check_writable(company)
        inner = (f'<STOCKGROUP NAME="{esc(POPUP_STOCK_GROUP)}" ACTION="Create">\n'
                 f'  <NAME.LIST><NAME>{esc(POPUP_STOCK_GROUP)}</NAME></NAME.LIST>\n  <PARENT/>\n</STOCKGROUP>')
        try:
            result = self.import_("All Masters", company, inner, timeout=timeout)
        except WriteTimeout:
            self.say("duplicate stock-group create timed out — Tally is showing its modal (expected)")
            return "timeout"
        return f"answered: created={result.created} altered={result.altered} errors={result.errors}"

    def export_report(self, company: str, report: str, from_date: str, to_date: str) -> int:
        """A TYPE=Data export — the automated stand-in for 'open this report in the UI'. Returns the response size."""
        return len(self.post(wrap_report(report, from_date, to_date, company), timeout=60.0).encode("utf-8"))

    def licence_info(self) -> LicenceInfo:
        return parse_licence_info(self.post(LICENCE_REQUEST, timeout=10.0))
```

- [x] **Step 10: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 31** (`test_setup_writes.py` 13 passed; `test_copied_headers.py` one more case).

---
### Task 3: Operator — config, Tally control under Wine, company-A lifecycle

**Files:**
- Create: `v2/probes/operator/__init__.py`, `v2/probes/operator/config.py`, `v2/probes/operator/tally_control.py`,
  `v2/probes/operator/company_a.py`
- Modify test double: `v2/tests/probes/fake_books.py` (append `FakeRunner`, `OWN_COMMAND`, `FOREIGN_COMMAND`, `tmp_config`)
- Test: `v2/tests/probes/test_tally_control.py`, `v2/tests/probes/test_company_a.py`

**Interfaces:**
- Consumes: `build_company_list`, `parse_company_list`, `sanitize_xml`, `ProbeBlocked`, `COMPANIES`, `SEED_COMPANY`,
  `TallyWriter`, `WriteFailed`
- Produces:
  - `config.OperatorConfig(wine_bin, tally_dir, data_dir, data_dir_windows, seed_dir, backups_dir, wine_log,
    company_numbers={"A": "100003"}, start_wait_s=240, stop_wait_s=20, click_wait_s=900, poll_s=3)` with `.edition`,
    `.company_folder(label)`, `.seed_folder(label)`; `default_config()`; `REPO_ROOT`, `DATA_MARKER = "s0probe"`
  - `tally_control.OperatorError(ProbeBlocked)`, `TallyProcess(pid, command)`, `ProcessRunner` (protocol: `list_tally`,
    `spawn`, `terminate`, `kill`, `run`, `sleep`, `now`), `SystemRunner`, `CLICK_NEEDED`,
    `TallyControl(config, runner, http, say, *, stop_any_tally=False)` with `port_up`, `company_names -> list | None`,
    `own_tally_running`, `stop`, `start(load_label)`, `wait_for_companies(expected, *, click)`, `restart(load_label,
    expected)`, `ensure_running`, `wine_version`
  - `company_a.replace_company_folder(source, target, config)`, `restore_seed_copy(control, config)`,
    `rename_seed_to_a(control, writer)`, `reset_company_a(control, writer, config)`, `backup_folder(config, label, tag)`,
    `backup_company(control, config, label, tag)`, `restore_company(control, config, label, tag)`
  - test double: `FakeRunner(books, procs=None, *, stubborn=False, hide_args=False)` with `.spawned`, `.terminated`,
    `.killed`, `.procs`; `tmp_config(tmp_path)`

- [x] **Step 1: Append the process double to `v2/tests/probes/fake_books.py`**

Add to the imports: `from v2.probes.operator.config import OperatorConfig` and
`from v2.probes.operator.tally_control import TallyProcess`. Append:

```python
OWN_COMMAND = r"C:\Program Files\TallyPrimeEditLog\tally.exe /DATA:C:\users\Public\TallyPrimeEditLog\s0probe /LOAD:100003"
FOREIGN_COMMAND = r"C:\Program Files\TallyPrimeEditLog\tally.exe"


def tmp_config(tmp_path: Path) -> OperatorConfig:
    """An operator config whose folders all live under `tmp_path` (the data folder is still named s0probe)."""
    return OperatorConfig(
        wine_bin=tmp_path / "wine" / "bin" / "wine",
        tally_dir=tmp_path / "Program Files" / "TallyPrimeEditLog",
        data_dir=tmp_path / "Public" / "TallyPrimeEditLog" / "s0probe",
        data_dir_windows=r"C:\users\Public\TallyPrimeEditLog\s0probe",
        seed_dir=tmp_path / "seed_data",
        backups_dir=tmp_path / "Public" / "TallyPrimeEditLog" / "s0probe-backups",
        wine_log=tmp_path / "logs" / "tally-wine.log",
        poll_s=1.0,
    )


class FakeRunner:
    """Stands in for ps / kill / Popen / sleep. Spawning 'Tally' starts FakeBooks; a virtual clock never sleeps."""

    def __init__(self, books: FakeBooks, procs: list[TallyProcess] | None = None, *, stubborn: bool = False,
                 hide_args: bool = False):
        self.books = books
        self.procs = list(procs or [])
        self.stubborn = stubborn          # terminate() doesn't stop it; kill() does
        self.hide_args = hide_args        # `ps` shows only the exe path, not /DATA:…
        self.clock = 0.0
        self.spawned: list[list[str]] = []
        self.terminated: list[int] = []
        self.killed: list[int] = []
        self.commands: list[list[str]] = []

    def list_tally(self) -> list[TallyProcess]:
        return list(self.procs)

    def spawn(self, argv: list[str], cwd: Path, log_path: Path) -> None:
        self.spawned.append(list(argv))
        command = FOREIGN_COMMAND if self.hide_args else " ".join(argv[1:])
        self.procs = [TallyProcess(100 + len(self.spawned), command)]
        self.books.start(load=any(arg.startswith("/LOAD:") for arg in argv))

    def terminate(self, pid: int) -> None:
        self.terminated.append(pid)
        if not self.stubborn:
            self._gone(pid)

    def kill(self, pid: int) -> None:
        self.killed.append(pid)
        self._gone(pid)

    def _gone(self, pid: int) -> None:
        self.procs = [p for p in self.procs if p.pid != pid]
        if not self.procs:
            self.books.stop()

    def run(self, argv: list[str], timeout: float) -> str:
        self.commands.append(list(argv))
        return "wine-11.0"

    def sleep(self, seconds: float) -> None:
        self.clock += seconds

    def now(self) -> float:
        return self.clock
```

- [x] **Step 2: Write the failing tests** — `v2/tests/probes/test_tally_control.py`

```python
from dataclasses import replace

import pytest

from v2.probes.companies import COMPANIES
from v2.probes.operator.tally_control import CLICK_NEEDED, OperatorError, TallyControl, TallyProcess
from v2.tests.probes.fake_books import FOREIGN_COMMAND, OWN_COMMAND, FakeBooks, FakeRunner, sync_client, tmp_config

A = COMPANIES["A"]


def _control(tmp_path, books, procs=(), *, stubborn=False, hide_args=False, stop_any_tally=False):
    runner = FakeRunner(books, list(procs), stubborn=stubborn, hide_args=hide_args)
    said: list[str] = []
    control = TallyControl(tmp_config(tmp_path), runner, sync_client(books.transport()), said.append,
                           stop_any_tally=stop_any_tally)
    return control, runner, said


def test_config_refuses_a_data_folder_that_is_not_s0probe(tmp_path):
    with pytest.raises(ValueError):
        replace(tmp_config(tmp_path), data_dir=tmp_path / "Data")


def test_config_refuses_backups_inside_s0probe(tmp_path):
    config = tmp_config(tmp_path)
    with pytest.raises(ValueError):
        replace(config, backups_dir=config.data_dir / "backups")


def test_stop_refuses_a_tally_it_did_not_start(tmp_path):
    books = FakeBooks(name=A)
    control, runner, _ = _control(tmp_path, books, [TallyProcess(7, FOREIGN_COMMAND)])
    with pytest.raises(OperatorError, match="didn't start"):
        control.stop()
    assert runner.terminated == [] and books.running


def test_stop_any_tally_flag_allows_it(tmp_path):
    books = FakeBooks(name=A)
    control, runner, _ = _control(tmp_path, books, [TallyProcess(7, FOREIGN_COMMAND)], stop_any_tally=True)
    control.stop()
    assert runner.terminated == [7] and not books.running


def test_stop_own_tally_recognised_by_its_data_argument(tmp_path):
    books = FakeBooks(name=A)
    control, runner, _ = _control(tmp_path, books, [TallyProcess(8, OWN_COMMAND)])
    control.stop()
    assert runner.terminated == [8] and runner.killed == [] and not books.running


def test_stubborn_tally_is_killed_after_the_wait(tmp_path):
    books = FakeBooks(name=A)
    control, runner, _ = _control(tmp_path, books, [TallyProcess(8, OWN_COMMAND)], stubborn=True)
    control.stop()
    assert runner.terminated == [8] and runner.killed == [8]


def test_start_passes_data_and_load_and_waits_for_the_port(tmp_path):
    books = FakeBooks(name=A, running=False, loaded=False)
    control, runner, _ = _control(tmp_path, books)
    control.start("A")
    assert runner.spawned == [[str(tmp_config(tmp_path).wine_bin), "tally.exe",
                               r"/DATA:C:\users\Public\TallyPrimeEditLog\s0probe", "/LOAD:100003"]]
    assert books.running and books.loaded


def test_start_refuses_when_tally_is_running(tmp_path):
    control, _, _ = _control(tmp_path, FakeBooks(name=A), [TallyProcess(8, OWN_COMMAND)])
    with pytest.raises(OperatorError, match="already running"):
        control.start(None)


def test_spawned_tally_is_ours_even_when_ps_hides_the_arguments(tmp_path):
    books = FakeBooks(name=A, running=False, loaded=False)
    control, runner, _ = _control(tmp_path, books, hide_args=True)
    control.start(None)
    assert runner.procs[0].command == FOREIGN_COMMAND
    control.stop()
    assert runner.terminated == [101]


def test_wait_for_companies_says_click_needed_and_rides_out_timeouts(tmp_path):
    books = FakeBooks(name=A, running=False, loaded=False, click_polls_on_load=2, busy_polls_on_load=2)
    control, _, said = _control(tmp_path, books)
    control.start("A")
    assert control.wait_for_companies([A], click=True) == [A]
    assert sum(line.startswith(CLICK_NEEDED) for line in said) == 1
    assert any("Tally busy" in line for line in said)


def test_wait_for_companies_times_out_after_the_click_window(tmp_path):
    books = FakeBooks(name=A, running=False, loaded=False, click_polls_on_load=100_000)
    control, _, said = _control(tmp_path, books)
    control.start("A")
    with pytest.raises(OperatorError, match="Timed out"):
        control.wait_for_companies([A], click=True)
    assert sum(line.startswith(CLICK_NEEDED) for line in said) > 1


def test_restart_without_company_needs_no_click(tmp_path):
    books = FakeBooks(name=A)
    control, runner, said = _control(tmp_path, books, [TallyProcess(8, OWN_COMMAND)])
    assert control.restart(None, []) == []
    assert not any(line.startswith(CLICK_NEEDED) for line in said)
    assert not any(arg.startswith("/LOAD:") for arg in runner.spawned[0])


def test_tally_ini_is_backed_up_once(tmp_path):
    config = tmp_config(tmp_path)
    config.tally_dir.mkdir(parents=True)
    (config.tally_dir / "tally.ini").write_text("Load=1\n", encoding="utf-8")
    books = FakeBooks(name=A, running=False, loaded=False)
    control, _, _ = _control(tmp_path, books)
    control.start(None)
    control.stop()
    (config.tally_dir / "tally.ini").write_text("Load=2\n", encoding="utf-8")
    control.start(None)
    assert (config.tally_dir / "tally.ini.before-s0").read_text(encoding="utf-8") == "Load=1\n"


def test_ensure_running_starts_tally_without_a_company(tmp_path):
    books = FakeBooks(name=A, running=False, loaded=False)
    control, runner, _ = _control(tmp_path, books)
    control.ensure_running()
    assert books.running and not books.loaded
    assert len(runner.spawned) == 1
    control.ensure_running()
    assert len(runner.spawned) == 1
```

`v2/tests/probes/test_company_a.py`:
```python
import json
from decimal import Decimal

import pytest

from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.operator import company_a
from v2.probes.operator.tally_control import CLICK_NEEDED, OperatorError, TallyControl, TallyProcess
from v2.probes.setup.writes import TallyWriter
from v2.tests.probes.fake_books import (FOREIGN_COMMAND, OWN_COMMAND, STATE_FILE, FakeBooks, FakeRunner, seed_state,
                                        sync_client, tmp_config, write_company_folder)

A = COMPANIES["A"]


def _setup(tmp_path, procs=(), dirty=True):
    config = tmp_config(tmp_path)
    write_company_folder(config.seed_folder("A"), SEED_COMPANY)
    write_company_folder(config.company_folder("A"), A)
    if dirty:                                      # what the throwaway run left: EMAIL on Electricity
        path = config.company_folder("A") / STATE_FILE
        state = json.loads(path.read_text(encoding="utf-8"))
        state["ledgers"]["Electricity"]["email"] = "s0probe@example.com"
        path.write_text(json.dumps(state), encoding="utf-8")
    books = FakeBooks(config.company_folder("A"), running=bool(procs), loaded=bool(procs), click_polls_on_load=1)
    runner = FakeRunner(books, list(procs))
    said: list[str] = []
    http = sync_client(books.transport())
    return config, books, runner, TallyControl(config, runner, http, said.append), TallyWriter(http, said.append), said


def test_reset_company_a_copies_the_seed_and_renames_it(tmp_path):
    config, books, runner, control, writer, said = _setup(tmp_path, [TallyProcess(8, OWN_COMMAND)])
    company_a.reset_company_a(control, writer, config)
    assert books.state == seed_state(A)                  # fresh seed data (no leftover EMAIL), renamed to A
    assert books.companies() == [A]
    assert runner.spawned[-1][-1] == "/LOAD:100003"
    assert any(line.startswith(CLICK_NEEDED) for line in said)


def test_reset_refuses_while_a_foreign_tally_runs_and_leaves_the_folder(tmp_path):
    config, books, _, control, writer, _ = _setup(tmp_path, [TallyProcess(7, FOREIGN_COMMAND)])
    with pytest.raises(OperatorError):
        company_a.reset_company_a(control, writer, config)
    assert books.state["ledgers"]["Electricity"]["email"] == "s0probe@example.com"


def test_replace_folder_refuses_a_target_outside_s0probe(tmp_path):
    config, *_ = _setup(tmp_path)
    with pytest.raises(OperatorError, match="Refusing"):
        company_a.replace_company_folder(config.seed_folder("A"), tmp_path / "elsewhere" / "100003", config)


def test_backup_then_restore_rolls_back_a_voucher(tmp_path):
    config, books, _, control, writer, _ = _setup(tmp_path, [TallyProcess(8, OWN_COMMAND)], dirty=False)
    company_a.backup_company(control, config, "A", "t1")
    assert (company_a.backup_folder(config, "A", "t1") / STATE_FILE).exists()
    writer.create_payment(A, ledger="Electricity", amount=Decimal("1"), narration="S0-throwaway 4")
    assert books.state["vouchers"]
    company_a.restore_company(control, config, "A", "t1")
    assert books.state["vouchers"] == {} and books.state["alt_vch"] == 50
    assert books.companies() == [A]


def test_seed_rename_needs_the_operators_own_tally(tmp_path):
    config, books, _, control, writer, _ = _setup(tmp_path)
    books.start(load=True)                              # a Tally we know nothing about (no process listed)
    with pytest.raises(OperatorError, match="own s0probe"):
        company_a.rename_seed_to_a(control, writer)
```

- [x] **Step 3: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_tally_control.py v2/tests/probes/test_company_a.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.operator'`.

- [x] **Step 4: Write `v2/probes/operator/__init__.py`**

```python
"""The automated operator (S0-D9, spec §5.8): performs every probe pause — XML edits through v2/probes/setup/,
open / close / restore through TallyPrime restarts under Wine. The person only clicks Tally's licence box."""
```

- [x] **Step 5: Write `v2/probes/operator/config.py`**

```python
"""Where the automated operator finds Wine, TallyPrime and the probe data folder (S0 spec §5.8; live 2026-09-22)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_MARKER = "s0probe"
WINE_BIN = Path("/Applications/Wine Stable.app/Contents/Resources/wine/bin/wine")
TALLY_DIR = Path.home() / ".wine/drive_c/Program Files/TallyPrimeEditLog"
DATA_DIR = Path.home() / ".wine/drive_c/users/Public/TallyPrimeEditLog" / DATA_MARKER
DATA_DIR_WINDOWS = r"C:\users\Public\TallyPrimeEditLog" + "\\" + DATA_MARKER


@dataclass(frozen=True)
class OperatorConfig:
    wine_bin: Path
    tally_dir: Path
    data_dir: Path                     # the s0probe folder, as the Mac sees it
    data_dir_windows: str              # the same folder as Tally sees it (for /DATA:)
    seed_dir: Path                     # repo seed_data/ — read-only source of the pristine company folder
    backups_dir: Path                  # beside s0probe, never inside it (Tally treats its data folder as companies)
    wine_log: Path                     # Wine's stdout / stderr
    company_numbers: dict[str, str] = field(default_factory=lambda: {"A": "100003"})
    start_wait_s: float = 240.0
    stop_wait_s: float = 20.0
    click_wait_s: float = 900.0        # the licence box waits up to 15 minutes for the person
    poll_s: float = 3.0

    def __post_init__(self) -> None:
        windows = self.data_dir_windows.rstrip("\\").lower()
        if self.data_dir.name != DATA_MARKER or not windows.endswith("\\" + DATA_MARKER):
            raise ValueError(f"Tally's data path must be the {DATA_MARKER!r} folder (S0 spec §5.8), got {self.data_dir}")
        if self.backups_dir.resolve().is_relative_to(self.data_dir.resolve()):
            raise ValueError("Backups must live outside the s0probe data folder")

    @property
    def edition(self) -> str:
        return "Edit Log" if "editlog" in self.tally_dir.name.lower() else "standard"

    def company_folder(self, label: str) -> Path:
        return self.data_dir / self.company_numbers[label]

    def seed_folder(self, label: str) -> Path:
        return self.seed_dir / self.company_numbers[label]


def default_config() -> OperatorConfig:
    return OperatorConfig(wine_bin=WINE_BIN, tally_dir=TALLY_DIR, data_dir=DATA_DIR, data_dir_windows=DATA_DIR_WINDOWS,
                          seed_dir=REPO_ROOT / "seed_data", backups_dir=DATA_DIR.parent / "s0probe-backups",
                          wine_log=REPO_ROOT / "v2" / "probes" / "results" / "logs" / "tally-wine.log")
```

- [x] **Step 6: Write `v2/probes/operator/tally_control.py`**

```python
"""Stop and start TallyPrime under Wine on the s0probe data folder, and wait for it (S0 spec §5.8).

Process control goes through a ProcessRunner so tests never start Wine. The operator stops only a TallyPrime it can
recognise as its own — started with /DATA:…s0probe, or spawned by this operator — unless told `stop_any_tally`.
"""
from __future__ import annotations

import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import httpx

from v2.agent.tally.envelopes import build_company_list
from v2.agent.tally.xml_utils import parse_company_list, sanitize_xml
from v2.probes.core import ProbeBlocked
from v2.probes.operator.config import DATA_MARKER, OperatorConfig

CLICK_NEEDED = "CLICK NEEDED: in TallyPrime click 'T: Continue In Educational Mode' on the licence box"
BUSY_REPEAT_S = 30.0
CLICK_REPEAT_S = 60.0


class OperatorError(ProbeBlocked):
    """The operator couldn't perform a step; the part is recorded BLOCKED with this message."""


@dataclass(frozen=True)
class TallyProcess:
    pid: int
    command: str


class ProcessRunner(Protocol):
    def list_tally(self) -> list[TallyProcess]: ...

    def spawn(self, argv: list[str], cwd: Path, log_path: Path) -> None: ...

    def terminate(self, pid: int) -> None: ...

    def kill(self, pid: int) -> None: ...

    def run(self, argv: list[str], timeout: float) -> str: ...

    def sleep(self, seconds: float) -> None: ...

    def now(self) -> float: ...


class SystemRunner:
    """The real ps / kill / Popen. Never used by tests."""

    def list_tally(self) -> list[TallyProcess]:
        out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, check=False).stdout
        found: list[TallyProcess] = []
        for line in out.splitlines():
            pid, _, command = line.strip().partition(" ")
            if pid.isdigit() and "tally.exe" in command.lower():
                found.append(TallyProcess(int(pid), command.strip()))
        return found

    def spawn(self, argv: list[str], cwd: Path, log_path: Path) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "ab") as log:
            subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=log, start_new_session=True)

    def terminate(self, pid: int) -> None:
        subprocess.run(["kill", "-TERM", str(pid)], check=False)

    def kill(self, pid: int) -> None:
        subprocess.run(["kill", "-KILL", str(pid)], check=False)

    def run(self, argv: list[str], timeout: float) -> str:
        try:
            done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""
        return done.stdout.strip()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> float:
        return time.monotonic()


class TallyControl:
    def __init__(self, config: OperatorConfig, runner: ProcessRunner, http: httpx.Client, say: Callable[[str], None],
                 *, stop_any_tally: bool = False):
        self.config = config
        self.runner = runner
        self.http = http
        self.say = say
        self.stop_any_tally = stop_any_tally
        self._own_pids: set[int] = set()

    # --- what is running ------------------------------------------------------------------------------------------
    def port_up(self) -> bool:
        try:
            return "Running" in self.http.get("/", timeout=httpx.Timeout(3.0, connect=3.0)).text
        except httpx.HTTPError:
            return False

    def company_names(self) -> list[str] | None:
        """Loaded companies, or None while Tally doesn't answer (starting, loading a company, stuck)."""
        try:
            response = self.http.post("/", content=build_company_list().encode("utf-8"),
                                      headers={"Content-Type": "text/xml; charset=utf-8"},
                                      timeout=httpx.Timeout(10.0, connect=3.0))
            response.raise_for_status()
            return parse_company_list(sanitize_xml(response.text))
        except (httpx.HTTPError, ET.ParseError):
            return None

    def _classify(self) -> tuple[list[TallyProcess], list[TallyProcess]]:
        own: list[TallyProcess] = []
        foreign: list[TallyProcess] = []
        for proc in self.runner.list_tally():
            if proc.pid in self._own_pids or DATA_MARKER in proc.command.lower():
                own.append(proc)
            else:
                foreign.append(proc)
        return own, foreign

    def own_tally_running(self) -> bool:
        own, foreign = self._classify()
        return bool(own) and not foreign

    # --- stop / start -----------------------------------------------------------------------------------------------
    def stop(self) -> None:
        own, foreign = self._classify()
        if foreign and not self.stop_any_tally:
            pids = ", ".join(str(p.pid) for p in foreign)
            raise OperatorError(f"A TallyPrime the operator didn't start is running (pid {pids}). Close it by hand, "
                                f"or pass --stop-any-tally; the operator only stops its own s0probe TallyPrime.")
        targets = own + foreign
        if not targets:
            return
        self.say(f"stopping TallyPrime (pid {', '.join(str(p.pid) for p in targets)})")
        for proc in targets:
            self.runner.terminate(proc.pid)
        if not self._wait(lambda: not self.runner.list_tally() and not self.port_up(), self.config.stop_wait_s):
            for proc in self.runner.list_tally():
                self.runner.kill(proc.pid)
            self.runner.sleep(2.0)
            if self.runner.list_tally():
                raise OperatorError("TallyPrime didn't stop, even after kill -9")
        self._own_pids.clear()

    def start(self, load_label: str | None) -> None:
        if self.runner.list_tally():
            raise OperatorError("TallyPrime is already running; stop it first")
        self._backup_ini_once()
        argv = [str(self.config.wine_bin), "tally.exe", f"/DATA:{self.config.data_dir_windows}"]
        if load_label is not None:
            argv.append(f"/LOAD:{self.config.company_numbers[load_label]}")
        self.say("starting TallyPrime: " + " ".join(argv[1:]))
        self.runner.spawn(argv, self.config.tally_dir, self.config.wine_log)

        def up() -> bool:
            self._own_pids.update(p.pid for p in self.runner.list_tally())   # nothing ran before the spawn
            return self.port_up()

        if not self._wait(up, self.config.start_wait_s):
            raise OperatorError(f"TallyPrime didn't answer on its port within {self.config.start_wait_s:.0f}s")

    def wait_for_companies(self, expected: list[str], *, click: bool) -> list[str] | None:
        """Poll the company list until it equals `expected`, riding out timeouts while a company loads."""
        limit = self.config.click_wait_s if click else self.config.start_wait_s
        deadline = self.runner.now() + limit
        told_at = busy_at = None
        if click:
            self.say(f"{CLICK_NEEDED} (waiting up to {limit / 60:.0f} min for {expected})")
            told_at = self.runner.now()
        while True:
            names = self.company_names()
            if names == expected:
                if click:
                    self.say(f"companies open: {names}")
                return names
            now = self.runner.now()
            if names is None and (busy_at is None or now - busy_at >= BUSY_REPEAT_S):
                self.say("Tally busy (loading a company?) — still waiting")
                busy_at = now
            if click and told_at is not None and now - told_at >= CLICK_REPEAT_S:
                self.say(f"{CLICK_NEEDED} (still waiting for {expected}; Tally shows {names})")
                told_at = now
            if now >= deadline:
                raise OperatorError(f"Timed out waiting for {expected}; Tally shows {names}")
            self.runner.sleep(self.config.poll_s)

    def restart(self, load_label: str | None, expected: list[str]) -> list[str] | None:
        self.stop()
        self.start(load_label)
        return self.wait_for_companies(expected, click=load_label is not None)

    def ensure_running(self) -> None:
        if self.port_up():
            return
        if self.runner.list_tally():
            raise OperatorError("A TallyPrime process exists but its port doesn't answer — check Tally for a popup")
        self.start(None)
        self.wait_for_companies([], click=False)

    def wine_version(self) -> str:
        return self.runner.run([str(self.config.wine_bin), "--version"], timeout=15.0)

    # --- helpers ------------------------------------------------------------------------------------------------------
    def _wait(self, condition: Callable[[], bool], seconds: float) -> bool:
        deadline = self.runner.now() + seconds
        while True:
            if condition():
                return True
            if self.runner.now() >= deadline:
                return False
            self.runner.sleep(1.0)

    def _backup_ini_once(self) -> None:
        ini = self.config.tally_dir / "tally.ini"
        backup = self.config.tally_dir / "tally.ini.before-s0"
        if ini.exists() and not backup.exists():
            shutil.copy2(ini, backup)
            self.say(f"backed up {ini.name} → {backup.name} (the operator never edits tally.ini)")
```

- [x] **Step 7: Write `v2/probes/operator/company_a.py`**

```python
"""Company A's lifecycle in automated mode (S0 spec §5.8): fresh seed copy, the rename, file-level backup / restore."""
from __future__ import annotations

import shutil
from pathlib import Path

from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.operator.config import OperatorConfig
from v2.probes.operator.tally_control import OperatorError, TallyControl
from v2.probes.setup.writes import TallyWriter, WriteFailed


def replace_company_folder(source: Path, target: Path, config: OperatorConfig) -> None:
    """Copy `source` over `target`; `target` must be a company folder directly inside the s0probe data folder."""
    if target.parent.resolve() != config.data_dir.resolve():
        raise OperatorError(f"Refusing to replace {target}: it isn't a company folder inside {config.data_dir}")
    if not source.is_dir():
        raise OperatorError(f"No company folder at {source}")
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def restore_seed_copy(control: TallyControl, config: OperatorConfig) -> None:
    """Stop Tally, copy the pristine seed company into s0probe, start Tally with it loaded (licence click)."""
    control.stop()
    replace_company_folder(config.seed_folder("A"), config.company_folder("A"), config)
    control.start("A")
    control.wait_for_companies([SEED_COMPANY], click=True)


def rename_seed_to_a(control: TallyControl, writer: TallyWriter) -> None:
    """The one write to a company without 'Probe' in its name — only on the operator's own s0probe TallyPrime."""
    if not control.own_tally_running():
        raise OperatorError("The seed rename runs only on the operator's own s0probe TallyPrime")
    try:
        writer.rename_company(SEED_COMPANY, COMPANIES["A"])
    except WriteFailed as exc:
        raise OperatorError(f"Company rename failed: {exc}") from exc


def reset_company_a(control: TallyControl, writer: TallyWriter, config: OperatorConfig) -> None:
    """`reset-a`: a fresh seed copy renamed to company A. Also undoes anything a probe could not revert."""
    restore_seed_copy(control, config)
    rename_seed_to_a(control, writer)


def backup_folder(config: OperatorConfig, label: str, tag: str) -> Path:
    return config.backups_dir / f"{config.company_numbers[label]}-{tag}"


def backup_company(control: TallyControl, config: OperatorConfig, label: str, tag: str) -> Path:
    """File-level backup with Tally stopped (a consistent copy), then Tally back up with the company."""
    control.stop()
    target = backup_folder(config, label, tag)
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(config.company_folder(label), target)
    control.start(label)
    control.wait_for_companies([COMPANIES[label]], click=True)
    return target


def restore_company(control: TallyControl, config: OperatorConfig, label: str, tag: str) -> None:
    """File-level restore of `backup_company`'s copy over the company folder (Tally's Restore screen isn't used)."""
    source = backup_folder(config, label, tag)
    control.stop()
    replace_company_folder(source, config.company_folder(label), config)
    control.start(label)
    control.wait_for_companies([COMPANIES[label]], click=True)
```

- [x] **Step 8: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 50** (`test_tally_control.py` 14 passed, `test_company_a.py` 5 passed).

---
### Task 4: `AutoOperator` + CLI `run --auto` / `reset-a` + run mode in results

**Files:**
- Create: `v2/probes/operator/auto.py`
- Modify: `v2/probes/__main__.py`, `v2/README.md`, `v2/tests/test_isolation.py`, `v2/tests/probes/test_cli.py`
- Test: `v2/tests/probes/test_auto_operator.py`

**Interfaces:**
- Consumes: `Action`, `PAUSE_KINDS`, `ASK_KINDS`, `TallyControl`, `SystemRunner`, `ProcessRunner`, `OperatorError`,
  `company_a.*`, `TallyWriter`, `WriteFailed`, `WriteRefused`, `GuardError`, `OperatorConfig`, `default_config`
- Produces:
  - `auto.AUTO_RUN_MODE` (the `run_mode` text stored in results), `OperatorLog(path=None, echo=print)` with `.write`,
    `.lines`; `AutoOperator(*, control, writer, config, log)` implementing `ProbeIO` (`interactive = True`,
    `run_mode = "auto"`, `wait`, `ask`, `say`), with `.vouchers: dict[ref, master_id]`, `.handled_pauses`,
    `.handled_asks`, `.reset_company_a()`, `.close()`;
    `build_auto_operator(*, host="localhost", port=9000, log_path=None, config=None, transport=None, runner=None,
    stop_any_tally=False, echo=None) -> AutoOperator`
  - CLI: `run … --auto [--stop-any-tally]`, `reset-a [--stop-any-tally]`; `main(argv, *, transport=None, io=None,
    operator=None)`; `MANUAL_RUN_MODE`; environment keys `run_mode`, `company_a_reset_at`
  - Action params the operator reads (probes must pass them):
    `open_company {label}`, `rename_company {from, to}`, `create_voucher {company, ref, ledger, amount, narration,
    post_dated?}`, `alter_voucher {company, ref, narration}`, `delete_voucher {company, ref}`, `create_ledger {company,
    name, parent}`, `alter_ledger {company, name, email}`, `delete_ledger {company, name}`, `rename_ledger {company, from,
    to}`, `view_report {company, report, from_date, to_date}`, `raise_popup {company}`, `dismiss_popup {label}`,
    `backup_company {label, tag}`, `restore_company {label, tag}`; `tally_running`, `restore_seed`,
    `close_all_companies`, `quit_tally` take none; ask `ui_closing_balance {ledger}`

- [x] **Step 1: Write the failing tests** — `v2/tests/probes/test_auto_operator.py`

```python
import pytest

from v2.probes.actions import ASK_KINDS, PAUSE_KINDS, Action
from v2.probes.companies import COMPANIES
from v2.probes.core import ProbeBlocked
from v2.probes.operator.auto import build_auto_operator
from v2.probes.operator.tally_control import CLICK_NEEDED, OperatorError, TallyProcess
from v2.tests.probes.fake_books import OWN_COMMAND, FakeBooks, FakeRunner, tmp_config

A = COMPANIES["A"]


def _operator(tmp_path, books=None, procs=None, log_path=None):
    books = books or FakeBooks(name=A)
    runner = FakeRunner(books, [TallyProcess(8, OWN_COMMAND)] if procs is None else procs)
    lines: list[str] = []
    op = build_auto_operator(config=tmp_config(tmp_path), transport=books.transport(), runner=runner,
                             log_path=log_path, echo=lines.append)
    return op, books, runner, lines


def _voucher(ref, **extra):
    return Action("create_voucher", {"company": A, "ref": ref, "ledger": "Electricity", "amount": "1.00",
                                     "narration": f"S0-throwaway {ref}", **extra})


def test_every_pause_and_ask_kind_has_a_handler(tmp_path):
    op, *_ = _operator(tmp_path)
    assert op.handled_pauses == PAUSE_KINDS
    assert op.handled_asks == ASK_KINDS


def test_a_pause_without_an_action_blocks_the_part(tmp_path):
    op, *_ = _operator(tmp_path)
    with pytest.raises(OperatorError) as info:
        op.wait("Do something clever in the UI")
    assert isinstance(info.value, ProbeBlocked)


def test_voucher_actions_track_master_ids(tmp_path):
    op, books, _, _ = _operator(tmp_path)
    op.wait("create", _voucher("r1"))
    assert op.vouchers == {"r1": "51"}
    op.wait("alter", Action("alter_voucher", {"company": A, "ref": "r1", "narration": "S0-throwaway r1 (altered)"}))
    assert books.state["vouchers"]["51"]["narration"] == "S0-throwaway r1 (altered)"
    op.wait("delete", Action("delete_voucher", {"company": A, "ref": "r1"}))
    assert op.vouchers == {} and books.state["vouchers"] == {}


def test_ledger_actions_go_through_the_writer(tmp_path):
    op, books, _, _ = _operator(tmp_path)
    op.wait("c", Action("create_ledger", {"company": A, "name": "S0 Probe Ledger", "parent": "Indirect Expenses"}))
    op.wait("a", Action("alter_ledger", {"company": A, "name": "S0 Probe Ledger", "email": "s0probe-1@example.com"}))
    op.wait("d", Action("delete_ledger", {"company": A, "name": "S0 Probe Ledger"}))
    op.wait("r", Action("rename_ledger", {"company": A, "from": "Rajesh Computers", "to": "Rajesh Computers S0"}))
    assert "Rajesh Computers S0" in books.state["ledgers"] and "S0 Probe Ledger" not in books.state["ledgers"]


def test_open_company_does_nothing_when_it_is_already_open(tmp_path):
    op, _, runner, _ = _operator(tmp_path)
    op.wait("open", Action("open_company", {"label": "A"}))
    assert runner.spawned == []


def test_open_company_restarts_with_load_and_asks_for_the_click(tmp_path):
    op, books, runner, lines = _operator(tmp_path, books=FakeBooks(name=A, loaded=False, click_polls_on_load=1))
    op.wait("open", Action("open_company", {"label": "A"}))
    assert runner.spawned[-1][-1] == "/LOAD:100003"
    assert books.companies() == [A]
    assert any(CLICK_NEEDED in line for line in lines)


def test_close_all_companies_restarts_without_a_company(tmp_path):
    op, books, runner, _ = _operator(tmp_path)
    op.wait("close", Action("close_all_companies"))
    assert not any(arg.startswith("/LOAD:") for arg in runner.spawned[-1])
    assert books.running and not books.loaded


def test_open_company_b_is_not_configured_yet(tmp_path):
    op, *_ = _operator(tmp_path)
    with pytest.raises(OperatorError, match="company B"):
        op.wait("open", Action("open_company", {"label": "B"}))


def test_asks_are_answered_from_tally_and_config(tmp_path):
    op, *_ = _operator(tmp_path)
    assert op.ask("wine?", Action("wine_version")) == "wine-11.0"
    assert op.ask("edition?", Action("edition")) == "Edit Log"
    assert op.ask("licence?", Action("licence")) == "educational"
    assert "7.0" in op.ask("version?", Action("tally_version"))
    assert r"s0probe\100003" in op.ask("folder?", Action("data_folder"))
    assert op.ask("balance?", Action("ui_closing_balance", {"ledger": "Cash"})) == ""


def test_expense_ledger_ask_has_no_scripted_answer(tmp_path):
    op, *_ = _operator(tmp_path)
    with pytest.raises(OperatorError):
        op.ask("Which expense ledger?", Action("expense_ledger"))


def test_write_failures_become_operator_errors(tmp_path):
    op, *_ = _operator(tmp_path)
    with pytest.raises(OperatorError, match="No voucher"):
        op.wait("delete", Action("delete_voucher", {"company": A, "ref": "never-created"}))
    with pytest.raises(OperatorError, match="Refusing"):
        op.wait("create", Action("create_voucher", {"company": "Bharat Traders Private Limited", "ref": "x",
                                                    "ledger": "Electricity", "amount": "1.00", "narration": "S0-x"}))


def test_popup_then_dismiss_restarts_tally(tmp_path):
    op, books, runner, lines = _operator(tmp_path)
    op.wait("popup", Action("raise_popup", {"company": A}))
    assert books.popup and any("→ timeout" in line for line in lines)
    op.wait("dismiss", Action("dismiss_popup", {"label": "A"}))
    assert not books.popup and books.companies() == [A]
    assert runner.spawned[-1][-1] == "/LOAD:100003"


def test_view_report_exports_instead_of_opening_the_ui(tmp_path):
    op, _, _, lines = _operator(tmp_path)
    op.wait("view", Action("view_report", {"company": A, "report": "Balance Sheet", "from_date": "01-04-2025",
                                           "to_date": "31-03-2026"}))
    assert any("exported 'Balance Sheet' via XML" in line for line in lines)


def test_every_step_is_logged_to_the_file(tmp_path):
    log = tmp_path / "logs" / "op.log"
    op, *_ = _operator(tmp_path, log_path=log)
    op.wait("create it", _voucher("r2"))
    op.ask("edition?", Action("edition"))
    text = log.read_text(encoding="utf-8")
    assert "STEP create_voucher" in text and "ASK  edition" in text
```

Add to `v2/tests/probes/test_cli.py` (imports at the top of the file):
```python
from v2.probes.actions import Action
from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.core import Probe
from v2.probes.operator.auto import AUTO_RUN_MODE, build_auto_operator
from v2.probes.operator.tally_control import TallyProcess
from v2.tests.probes.fake_books import OWN_COMMAND, FakeBooks, FakeRunner, tmp_config, write_company_folder
```
and these tests (append):
```python
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
```

Add to `v2/tests/test_isolation.py`:
```python
def test_probe_modules_never_import_write_code():
    offenders = []
    for path in sorted((V2_ROOT / "probes").glob("p[0-9][0-9]_*.py")):
        modules = imported_modules(path.read_text(encoding="utf-8"))
        if any(m.startswith(("v2.probes.setup", "v2.probes.operator")) for m in modules):
            offenders.append(path.name)
    assert offenders == []
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_auto_operator.py v2/tests/probes/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.operator.auto'`.

- [x] **Step 3: Write `v2/probes/operator/auto.py`**

```python
"""The automated operator (S0-D9, spec §5.8): implements ProbeIO by performing each pause and answering each ask.

It dispatches on Action.kind only (never on the instruction text). Writes go through TallyWriter (verified shapes,
read back, "Probe" companies only); open / close / backup / restore go through TallyControl restarts under Wine.
Every step is written to the operator log.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import httpx

from v2.probes.actions import ASK_KINDS, PAUSE_KINDS, Action
from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.operator import company_a
from v2.probes.operator.config import OperatorConfig, default_config
from v2.probes.operator.tally_control import OperatorError, ProcessRunner, SystemRunner, TallyControl
from v2.probes.safety import GuardError
from v2.probes.setup.writes import TallyWriter, WriteFailed, WriteRefused

AUTO_RUN_MODE = (
    "auto (S0-D9): the operator performs every pause — edits via XML import (verified shapes, read back), open/close "
    "via TallyPrime restarts under Wine with /DATA and /LOAD, company-A restore/backup by copying the company folder. "
    "Not exercised: UI-edit parity for probes 1, 7, 8 and probe 16's UI balance read (later manual checks); probe 10's "
    "popup is a deliberate duplicate-master create; probe 13 restores at file level (Tally's Backup/Restore screens "
    "unused)."
)


class OperatorLog:
    """Every operator line goes to `echo` (stdout by default) and, when a path is given, to a log file."""

    def __init__(self, path: Path | None = None, echo: Callable[[str], None] | None = None):
        self.path = path
        self.echo = echo or (lambda line: print(line, flush=True))
        self.lines: list[str] = []

    def write(self, message: str) -> None:
        line = f"[operator {datetime.now().strftime('%H:%M:%S')}] {message}"
        self.lines.append(line)
        self.echo(line)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


class AutoOperator:
    interactive = True
    run_mode = "auto"

    def __init__(self, *, control: TallyControl, writer: TallyWriter, config: OperatorConfig, log: OperatorLog):
        self.control = control
        self.writer = writer
        self.config = config
        self.log = log
        self.vouchers: dict[str, str] = {}          # a probe's voucher ref → Tally Master ID
        self._pause: dict[str, Callable[[dict[str, Any]], None]] = {
            "tally_running": self._tally_running, "restore_seed": self._restore_seed,
            "rename_company": self._rename_company, "close_all_companies": self._close_all,
            "open_company": self._open_company, "create_voucher": self._create_voucher,
            "alter_voucher": self._alter_voucher, "delete_voucher": self._delete_voucher,
            "create_ledger": self._create_ledger, "alter_ledger": self._alter_ledger,
            "delete_ledger": self._delete_ledger, "rename_ledger": self._rename_ledger,
            "view_report": self._view_report, "raise_popup": self._raise_popup, "dismiss_popup": self._dismiss_popup,
            "quit_tally": self._quit_tally, "backup_company": self._backup_company,
            "restore_company": self._restore_company,
        }
        self._ask: dict[str, Callable[[dict[str, Any]], str]] = {
            "wine_version": self._wine_version, "data_folder": self._data_folder, "tally_version": self._tally_version,
            "edition": self._edition, "licence": self._licence, "expense_ledger": self._expense_ledger,
            "ui_closing_balance": self._ui_closing_balance,
        }
        if set(self._pause) != PAUSE_KINDS or set(self._ask) != ASK_KINDS:
            raise RuntimeError("AutoOperator handlers are out of step with actions.PAUSE_KINDS / ASK_KINDS")

    @property
    def handled_pauses(self) -> frozenset[str]:
        return frozenset(self._pause)

    @property
    def handled_asks(self) -> frozenset[str]:
        return frozenset(self._ask)

    # --- ProbeIO ----------------------------------------------------------------------------------------------------
    def say(self, message: str) -> None:
        self.log.write(message)

    def wait(self, instruction: str, action: Action | None = None) -> None:
        if action is None or action.kind not in self._pause:
            raise OperatorError(f"No automated action for this step: {instruction}")
        self.log.write(f"STEP {action.kind} {action.params or ''} — {instruction}")
        try:
            self._pause[action.kind](action.params)
        except (WriteFailed, WriteRefused, GuardError) as exc:
            raise OperatorError(f"{action.kind}: {exc}") from exc

    def ask(self, prompt: str, action: Action | None = None) -> str:
        if action is None or action.kind not in self._ask:
            raise OperatorError(f"No automated answer for: {prompt}")
        try:
            answer = self._ask[action.kind](action.params)
        except (WriteFailed, GuardError) as exc:
            raise OperatorError(f"{action.kind}: {exc}") from exc
        self.log.write(f"ASK  {action.kind}: {prompt!r} → {answer!r}")
        return answer

    # --- commands ---------------------------------------------------------------------------------------------------
    def reset_company_a(self) -> None:
        self.log.write("reset-a: fresh copy of the seed company into s0probe, then rename it to company A")
        try:
            company_a.reset_company_a(self.control, self.writer, self.config)
        except (WriteFailed, WriteRefused, GuardError) as exc:
            raise OperatorError(f"reset-a: {exc}") from exc
        self.vouchers.clear()

    def close(self) -> None:
        self.writer.http.close()

    # --- pause handlers ---------------------------------------------------------------------------------------------
    def _tally_running(self, params: dict[str, Any]) -> None:
        self.control.ensure_running()

    def _restore_seed(self, params: dict[str, Any]) -> None:
        company_a.restore_seed_copy(self.control, self.config)

    def _rename_company(self, params: dict[str, Any]) -> None:
        if params["from"] == SEED_COMPANY and params["to"] == COMPANIES["A"]:
            company_a.rename_seed_to_a(self.control, self.writer)
        else:
            self.writer.rename_company(params["from"], params["to"])

    def _close_all(self, params: dict[str, Any]) -> None:
        self.control.restart(None, [])

    def _open_company(self, params: dict[str, Any]) -> None:
        label = params["label"]
        if label not in self.config.company_numbers:
            raise OperatorError(f"Auto mode can't open company {label} yet: no company number configured (plan part 3)")
        wanted = [COMPANIES[label]]
        if self.control.company_names() == wanted:
            self.log.write(f"company {label} is already the only open company")
            return
        self.control.restart(label, wanted)

    def _master_id(self, ref: str) -> str:
        if ref not in self.vouchers:
            raise OperatorError(f"No voucher {ref!r} was created in this run")
        return self.vouchers[ref]

    def _create_voucher(self, params: dict[str, Any]) -> None:
        ref = params["ref"]
        if ref in self.vouchers:
            raise OperatorError(f"Voucher ref {ref!r} is already in use in this run")
        self.vouchers[ref] = self.writer.create_payment(
            params["company"], ledger=params["ledger"], amount=Decimal(params["amount"]), narration=params["narration"],
            post_dated=bool(params.get("post_dated", False)))

    def _alter_voucher(self, params: dict[str, Any]) -> None:
        self.writer.alter_voucher_narration(params["company"], self._master_id(params["ref"]), params["narration"])

    def _delete_voucher(self, params: dict[str, Any]) -> None:
        self.writer.delete_voucher(params["company"], self._master_id(params["ref"]))
        self.vouchers.pop(params["ref"])

    def _create_ledger(self, params: dict[str, Any]) -> None:
        self.writer.create_ledger(params["company"], params["name"], params["parent"])

    def _alter_ledger(self, params: dict[str, Any]) -> None:
        self.writer.alter_ledger_email(params["company"], params["name"], params["email"])

    def _delete_ledger(self, params: dict[str, Any]) -> None:
        self.writer.delete_ledger(params["company"], params["name"])

    def _rename_ledger(self, params: dict[str, Any]) -> None:
        self.writer.rename_ledger(params["company"], params["from"], params["to"])

    def _view_report(self, params: dict[str, Any]) -> None:
        size = self.writer.export_report(params["company"], params["report"], params["from_date"], params["to_date"])
        self.log.write(f"exported {params['report']!r} via XML instead of opening it in the UI ({size} bytes)")

    def _raise_popup(self, params: dict[str, Any]) -> None:
        self.log.write(f"duplicate stock-group create → {self.writer.raise_duplicate_master_popup(params['company'])}")

    def _dismiss_popup(self, params: dict[str, Any]) -> None:
        label = params["label"]
        self.control.restart(label, [COMPANIES[label]])

    def _quit_tally(self, params: dict[str, Any]) -> None:
        self.control.stop()

    def _backup_company(self, params: dict[str, Any]) -> None:
        folder = company_a.backup_company(self.control, self.config, params["label"], params["tag"])
        self.log.write(f"file-level backup of company {params['label']} → {folder}")

    def _restore_company(self, params: dict[str, Any]) -> None:
        company_a.restore_company(self.control, self.config, params["label"], params["tag"])

    # --- ask handlers -----------------------------------------------------------------------------------------------
    def _wine_version(self, params: dict[str, Any]) -> str:
        version = self.control.wine_version()
        if not version:
            raise OperatorError("`wine --version` printed nothing")
        return version

    def _data_folder(self, params: dict[str, Any]) -> str:
        number = self.config.company_numbers["A"]
        return f"{self.config.data_dir_windows}\\{number} (fresh copy of seed_data/{number} made by the operator)"

    def _tally_version(self, params: dict[str, Any]) -> str:
        info = self.writer.licence_info()
        if not info.release:
            return "TallyPrime (release not in the XML response header)"
        return f"TallyPrime {info.release} (release from the XML response header)"

    def _edition(self, params: dict[str, Any]) -> str:
        return self.config.edition

    def _licence(self, params: dict[str, Any]) -> str:
        info = self.writer.licence_info()
        if info.educational is None:
            raise OperatorError("$$LicenseInfo:IsEducationalMode gave no Yes/No answer")
        return "educational" if info.educational else "licensed"

    def _expense_ledger(self, params: dict[str, Any]) -> str:
        raise OperatorError("No Indirect Expenses ledger found and no scripted answer — pick one by hand")

    def _ui_closing_balance(self, params: dict[str, Any]) -> str:
        return ""     # auto mode reads no UI; probe 16 records the UI comparison as not done


def build_auto_operator(*, host: str = "localhost", port: int = 9000, log_path: Path | None = None,
                        config: OperatorConfig | None = None, transport: httpx.BaseTransport | None = None,
                        runner: ProcessRunner | None = None, stop_any_tally: bool = False,
                        echo: Callable[[str], None] | None = None) -> AutoOperator:
    config = config or default_config()
    log = OperatorLog(log_path, echo)
    http = httpx.Client(base_url=f"http://{host}:{port}", transport=transport, trust_env=False)
    control = TallyControl(config, runner or SystemRunner(), http, log.write, stop_any_tally=stop_any_tally)
    return AutoOperator(control=control, writer=TallyWriter(http, log.write), config=config, log=log)
```

- [x] **Step 4: Replace `v2/probes/__main__.py`**

```python
"""Runner CLI: python -m v2.probes {list,run,report,reset-a} (S0 spec §5.3, §5.8)."""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, datetime
from pathlib import Path

import httpx

from v2.agent.tally.client import TallyClient
from v2.probes.actions import Action
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.console import ConsoleIO, ProbeIO
from v2.probes.core import Outcome, ProbeBlocked
from v2.probes.operator.auto import AUTO_RUN_MODE, AutoOperator, build_auto_operator
from v2.probes.operator.tally_control import OperatorError
from v2.probes.registry import ALL_ORDER, FIRST_ORDER, PROBES, load_probe
from v2.probes.report import render_report
from v2.probes.results import ResultsStore
from v2.probes.runner import run_order, run_probe

V2_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = V2_ROOT / "probes" / "results" / "results.json"
FIXTURES_DIR = V2_ROOT / "tests" / "fixtures" / "sync"
LOGS_DIR = V2_ROOT / "probes" / "results" / "logs"
DOCS_DIR = V2_ROOT.parent / "docs"
MAX_PROBE_ID = PROBES[-1].id
MANUAL_RUN_MODE = "manual (S0-D3): a person performs each pause at the Tally UI"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m v2.probes")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--fixtures", type=Path, default=FIXTURES_DIR)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    run = sub.add_parser("run")
    which = run.add_mutually_exclusive_group(required=True)
    which.add_argument("probe_id", nargs="?", type=int)
    which.add_argument("--first", action="store_true")
    which.add_argument("--all", action="store_true")
    run.add_argument("--company", choices=["A", "B", "C"])
    run.add_argument("--rerun", action="store_true")
    run.add_argument("--auto", action="store_true", help="the automated operator performs every pause (S0-D9)")
    run.add_argument("--stop-any-tally", action="store_true",
                     help="with --auto: the operator may stop a TallyPrime it didn't start")
    report = sub.add_parser("report")
    report.add_argument("--out", type=Path)
    reset = sub.add_parser("reset-a", help="fresh seed copy in s0probe, renamed to company A (S0 spec §5.8)")
    reset.add_argument("--stop-any-tally", action="store_true")
    return parser


def _status(store: ResultsStore, item) -> str:
    if item.deferred:
        return "⏭ deferred (Q29)"
    outcome = store.outcome(item.id)
    if outcome is None:
        return "not run" if item.module else "not built"
    if outcome is Outcome.PARTIAL:
        remaining = store.probe_entry(item.id).get("remaining") or []
        if remaining:
            return f"PARTIAL (remaining: {', '.join(remaining)})"
    return outcome.value


def _list(store: ResultsStore) -> int:
    for item in PROBES:
        print(f"{item.id:>2}  {item.name:<28} {item.companies:<5} {item.tier:<4} {_status(store, item)}")
    return 0


def _auto_log() -> Path:
    return LOGS_DIR / f"s0-auto-{date.today().isoformat()}.log"


async def _run(args, store: ResultsStore, transport: httpx.AsyncBaseTransport | None, io: ProbeIO) -> int:
    client = TallyClient(args.host, args.port, transport=transport)
    capture = Capture(args.fixtures)
    try:
        if args.first or args.all:
            await run_order(FIRST_ORDER if args.first else ALL_ORDER, client=client, store=store, capture=capture,
                            io=io, rerun=args.rerun)
            return 0
        if not 0 <= args.probe_id <= MAX_PROBE_ID:
            print(f"No probe {args.probe_id} (probes are 0–{MAX_PROBE_ID}).")
            return 2
        probe = load_probe(args.probe_id)
        if probe is None:
            print(f"Probe {args.probe_id} is not built yet (S0 plan part 2 or 3).")
            return 2
        if args.company and args.company not in probe.parts:
            print(f"Probe {args.probe_id} has no part {args.company} (has {', '.join(sorted(probe.parts))}).")
            return 2
        labels = [args.company] if args.company else None
        if getattr(io, "run_mode", "manual") == "auto" and probe.guard:
            first = labels[0] if labels else next(iter(probe.parts))
            try:
                io.wait(f"Open company {first}: {COMPANIES[first]!r}", Action("open_company", {"label": first}))
            except ProbeBlocked as exc:
                print(f"Couldn't open company {first}: {exc}")
                return 1
        await run_probe(probe, labels=labels, client=client, store=store, capture=capture, io=io)
        return 0
    finally:
        await client.close()


def _reset_a(args, store: ResultsStore, operator: AutoOperator | None) -> int:
    auto = operator or build_auto_operator(host=args.host, port=args.port, log_path=_auto_log(),
                                           stop_any_tally=args.stop_any_tally)
    try:
        auto.reset_company_a()
    except OperatorError as exc:
        print(f"reset-a failed: {exc}")
        return 1
    finally:
        if operator is None:
            auto.close()
    store.update_environment(company_a_reset_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    print(f"Company A reset: a fresh copy of the seed company, renamed to {COMPANIES['A']!r}.")
    return 0


def main(argv: list[str] | None = None, *, transport: httpx.AsyncBaseTransport | None = None,
         io: ProbeIO | None = None, operator: AutoOperator | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "run" and args.company and (args.first or args.all):
        parser.error("--company cannot be used with --first/--all")
    if args.command == "run" and args.auto and args.non_interactive:
        parser.error("--auto cannot be used with --non-interactive")
    store = ResultsStore(args.results)
    if args.command == "list":
        return _list(store)
    if args.command == "report":
        out = args.out or DOCS_DIR / f"bi-s0-probe-results-{date.today().isoformat()}.md"
        out.write_text(render_report(store, date.today().isoformat()), encoding="utf-8")
        print(f"Wrote {out}")
        return 0
    if args.command == "reset-a":
        return _reset_a(args, store, operator)
    if args.auto:
        auto = operator or build_auto_operator(host=args.host, port=args.port, log_path=_auto_log(),
                                               stop_any_tally=args.stop_any_tally)
        store.update_environment(run_mode=AUTO_RUN_MODE)
        try:
            return asyncio.run(_run(args, store, transport, auto))
        finally:
            if operator is None:
                auto.close()
    store.update_environment(run_mode=MANUAL_RUN_MODE)
    return asyncio.run(_run(args, store, transport, io or ConsoleIO(interactive=not args.non_interactive)))


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 5: Document the automated mode in `v2/README.md`** (append):

```markdown
## Automated runs (S0-D9, S0 spec §5.8)
- `uv run --project v2 python -m v2.probes reset-a` — stops the operator's TallyPrime, copies the pristine
  `seed_data/100003` into `s0probe`, starts Tally with `/DATA:… /LOAD:100003` and renames the company to
  "Bharat Traders Probe Copy". Also undoes anything a probe couldn't revert.
- `uv run --project v2 python -m v2.probes run --all --auto` (or `run <id> --auto`) — the operator performs every pause:
  edits via XML import (read back), open/close/backup/restore via Tally restarts.
- Watch for **`CLICK NEEDED`**: after every restart that loads a company, click "T: Continue In Educational Mode" on
  Tally's licence box (the operator waits up to 15 minutes).
- The operator stops only a TallyPrime it started on `s0probe` (`--stop-any-tally` overrides) and never edits
  `tally.ini` (it backs it up once as `tally.ini.before-s0`). Log: `v2/probes/results/logs/s0-auto-<date>.log`.
```

- [x] **Step 6: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 69** (`test_auto_operator.py` 14, `test_cli.py` +4, `test_isolation.py` +1).

---
### Task 5: Probe 1 revision — master steps on the throwaway ledger

**Files:**
- Modify: `v2/probes/p01_company_counters.py` (whole file)
- Test: `v2/tests/probes/test_p01_company_counters.py` (whole file)

**Interfaces:**
- Consumes: `ProbeContext.send/counters/pause/ask/observe/confirm_request/on_abort/resolve_abort`, `select_company`,
  `Action`, `THROWAWAY_DATE_TEXT`; for the end-to-end test `build_auto_operator`, `FakeBooks`, `FakeRunner`
- Produces: `PROBE` (id 1, part "A", `requires=(0,)`, `mutating`, `educational_sensitive`), `CANDIDATE_FIELDS`,
  `COUNTERS_REQUEST` (unchanged — the confirmed request other probes use), `THROWAWAY_LEDGER = "S0 Probe Ledger"`,
  `THROWAWAY_PARENT`, `VOUCHER_REF = "p01-v1"`, `EMAILS`, `actions_for(company, ledger) -> list[(step, kind,
  instruction, Action)]` (replaces the part-1 `ACTIONS` list), `DELETE_VOUCHER_NOTE`, `DELETE_LEDGER_NOTE`
- Steps (spec §11.5 + changes): `counters_candidates`, `ledger_list`, **`throwaway_ledger_check`** (new),
  `counters_baseline`, `ledger_before`, `counters_after_{create,alter,delete}_voucher`, `ledger_after_voucher`,
  `counters_after_{create,alter,alter_again,delete}_ledger` (**`alter_again`** new; the old `revert_ledger` is gone)

Pause instructions (the operator performs the Action; a person follows the text):
1. `create_voucher` — "Create a Payment voucher dated 31-Mar-2026: Cash → {ledger}, ₹1, narration 'S0-throwaway 1'. Save it."
2. `alter_voucher` — "Alter that voucher's narration to 'S0-throwaway 1 (altered)' and save." (a header field — the
   verified alter by Master ID; an amount alter risks a duplicate, LESSONS §10)
3. `delete_voucher` — "Delete that voucher (open it, Alt+D)."
4. `create_ledger` — "Create a ledger 'S0 Probe Ledger' under Indirect Expenses."
5. `alter_ledger` — "Alter ledger 'S0 Probe Ledger': set its E-Mail to 's0probe-1@example.com' and save."
6. `alter_ledger` (again) — "… set its E-Mail to 's0probe-2@example.com' …"
7. `delete_ledger` — "Delete ledger 'S0 Probe Ledger'."

Outcome rules (unchanged in substance): **FAILED** if AltVchId/AltMstId don't come back (spec impact: rolling re-pull,
R6); **DIFFERENT** if a voucher step doesn't move AltVchId, a master step doesn't move AltMstId, or the voucher entry
moves the expense ledger's AlterID; **BLOCKED** if the throwaway ledger already exists (a duplicate create would freeze
Tally); **CONFIRMED** otherwise. Company A ends as it was: the voucher and the throwaway ledger are gone and the existing
ledger is never altered.

- [x] **Step 1: Write the failing tests** — replace `v2/tests/probes/test_p01_company_counters.py`

```python
import httpx

from v2.agent.tally.client import TallyClient
from v2.probes import p01_company_counters as p01
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.core import Outcome
from v2.probes.operator.auto import build_auto_operator
from v2.probes.operator.tally_control import TallyProcess
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import OWN_COMMAND, FakeBooks, FakeRunner, seed_state, tmp_config
from v2.tests.probes.fakes import FakeTally, ScriptedIO, make_harness, mark_done, objects_xml

A = COMPANIES["A"]


def _state(expense="Bank Charges"):
    return {"AltVchId": 100, "AltMstId": 50, "ledger": 7, "expense": expense}


def _fake(state, include_counters=True, ledgers=None, throwaway_exists=False):
    fake = FakeTally([A])

    def counters(body):
        row = {"Name": A, "GUID": "g-1", "BooksFrom": "20250401", "LastVoucherDate": "20260301", "AlterID": "1"}
        if include_counters:
            row.update(AltVchId=str(state["AltVchId"]), AltMstId=str(state["AltMstId"]))
        return objects_xml("COMPANY", [row])

    def one_ledger(body):
        if p01.THROWAWAY_LEDGER in body:
            rows = [{"Name": p01.THROWAWAY_LEDGER, "GUID": "l-9", "AlterID": "9"}] if throwaway_exists else []
            return objects_xml("LEDGER", rows)
        return objects_xml("LEDGER", [{"Name": state["expense"], "GUID": "l-1", "AlterID": str(state["ledger"])}])

    fake.route("S0CompanyCounters", counters)
    fake.route("S0LedgerList", lambda body: objects_xml("LEDGER", ledgers or [
        {"Name": "Cash", "Parent": "Cash-in-Hand"}, {"Name": "Bank Charges", "Parent": "Indirect Expenses"}]))
    fake.route("S0OneLedger", one_ledger)
    return fake


def _io(state, skip=(), voucher_moves_ledger=False):
    fields = {"create_voucher": "AltVchId", "alter_voucher": "AltVchId", "delete_voucher": "AltVchId",
              "create_ledger": "AltMstId", "alter_ledger": "AltMstId", "delete_ledger": "AltMstId"}
    alters = {"n": 0}

    def on_action(action):
        step = action.kind
        if step == "alter_ledger":
            alters["n"] += 1
            step = "alter_ledger" if alters["n"] == 1 else "alter_ledger_again"
        if step in skip:
            return
        state[fields[action.kind]] += 1
        if action.kind == "create_voucher" and voucher_moves_ledger:
            state["ledger"] += 1

    return ScriptedIO(on_action=on_action)


async def _run(tmp_path, fake, io):
    client, store, capture = make_harness(tmp_path, fake)
    mark_done(store, 0, part="A")
    outcome = await run_probe(p01.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return outcome, store


async def test_expected_counters_confirmed_and_request_stored(tmp_path):
    state = _state()
    outcome, store = await _run(tmp_path, _fake(state), _io(state))
    part = store.probe_entry(1)["parts"]["A"]
    assert outcome is Outcome.CONFIRMED, part["summary"]
    confirmed = store.confirmed("company_counters")
    assert confirmed["xml_template"] == p01.COUNTERS_REQUEST
    assert confirmed["fields"] == ["GUID", "AltVchId", "AltMstId", "BooksFrom", "LastVoucherDate", "AlterID"]
    assert part["observations"]["ledger"] == "Bank Charges"
    assert list(part["observations"]["matrix"]) == ["create_voucher", "alter_voucher", "delete_voucher",
                                                     "create_ledger", "alter_ledger", "alter_ledger_again",
                                                     "delete_ledger"]
    assert part["observations"]["ledger_alterid_moved_on_voucher_entry"] is False
    assert "p01_A_counters_after_alter_ledger_again.xml" in part["fixtures"]
    assert "p01_A_throwaway_ledger_check.xml" in part["fixtures"]


async def test_master_steps_run_on_the_throwaway_ledger_only(tmp_path):
    state = _state()
    io = _io(state)
    await _run(tmp_path, _fake(state), io)
    kinds = [a.kind for a in io.actions]
    assert kinds == ["create_voucher", "alter_voucher", "delete_voucher", "create_ledger", "alter_ledger",
                     "alter_ledger", "delete_ledger"]
    masters = [a for a in io.actions if a.kind.endswith("_ledger")]
    assert {a.params["name"] for a in masters} == {p01.THROWAWAY_LEDGER}
    emails = [a.params["email"] for a in masters if a.kind == "alter_ledger"]
    assert emails == list(p01.EMAILS) and all(emails)            # never an empty-value alter
    assert io.actions[0].params["ledger"] == "Bank Charges"      # the voucher uses the existing expense ledger


async def test_counter_not_moving_is_different(tmp_path):
    state = _state()
    outcome, store = await _run(tmp_path, _fake(state), _io(state, skip=("delete_voucher",)))
    part = store.probe_entry(1)["parts"]["A"]
    assert outcome is Outcome.DIFFERENT
    assert "AltVchId did not move on delete_voucher" in part["summary"]
    assert "R6" in part["spec_impact"]


async def test_second_alter_not_moving_is_different(tmp_path):
    state = _state()
    outcome, store = await _run(tmp_path, _fake(state), _io(state, skip=("alter_ledger_again",)))
    assert outcome is Outcome.DIFFERENT
    assert "AltMstId did not move on alter_ledger_again" in store.probe_entry(1)["parts"]["A"]["summary"]


async def test_voucher_moving_ledger_alterid_is_different(tmp_path):
    state = _state()
    outcome, store = await _run(tmp_path, _fake(state), _io(state, voucher_moves_ledger=True))
    assert outcome is Outcome.DIFFERENT
    assert "ledger's own AlterID" in store.probe_entry(1)["parts"]["A"]["summary"]


async def test_missing_counters_fail_and_nothing_confirmed(tmp_path):
    state = _state()
    outcome, store = await _run(tmp_path, _fake(state, include_counters=False), _io(state))
    part = store.probe_entry(1)["parts"]["A"]
    assert outcome is Outcome.FAILED
    assert "rolling re-pull" in part["spec_impact"]
    assert store.confirmed("company_counters") is None


async def test_fallback_ledger_used_when_no_bank_charges(tmp_path):
    state = _state(expense="Electricity")
    fake = _fake(state, ledgers=[{"Name": "Cash", "Parent": "Cash-in-Hand"},
                                 {"Name": "Electricity", "Parent": "Indirect Expenses"},
                                 {"Name": "Salaries", "Parent": "Indirect Expenses"}])
    outcome, store = await _run(tmp_path, fake, _io(state))
    part = store.probe_entry(1)["parts"]["A"]
    assert outcome is Outcome.CONFIRMED, part["summary"]
    assert part["observations"]["ledger"] == "Electricity"


async def test_without_probe0_confirmed_blocks(tmp_path):
    state = _state()
    client, store, capture = make_harness(tmp_path, _fake(state))
    outcome = await run_probe(p01.PROBE, labels=None, client=client, store=store, capture=capture, io=_io(state))
    assert outcome is Outcome.BLOCKED
    assert "Run probe(s) 0 first." in store.probe_entry(1)["parts"]["A"]["summary"]


async def test_existing_throwaway_ledger_blocks_before_any_change(tmp_path):
    state = _state()
    io = _io(state)
    outcome, store = await _run(tmp_path, _fake(state, throwaway_exists=True), io)
    assert outcome is Outcome.BLOCKED
    assert "already exists" in store.probe_entry(1)["parts"]["A"]["summary"]
    assert io.actions == []


async def test_cleanup_note_pending_when_blocked_after_create_ledger(tmp_path):
    state = _state()
    fake = _fake(state)
    calls = {"n": 0}
    others = [(marker, handler) for marker, handler in fake.routes if marker != "S0CompanyCounters"]

    def counters(body):
        calls["n"] += 1
        if calls["n"] == 6:   # candidates, baseline, 3 voucher steps, then the read after create_ledger
            return httpx.ReadTimeout
        row = {"Name": A, "GUID": "g-1", "BooksFrom": "20250401", "LastVoucherDate": "20260301", "AlterID": "1",
               "AltVchId": str(state["AltVchId"]), "AltMstId": str(state["AltMstId"])}
        return objects_xml("COMPANY", [row])

    fake.routes = [("S0CompanyCounters", counters), *others]
    outcome, store = await _run(tmp_path, fake, _io(state))
    part = store.probe_entry(1)["parts"]["A"]
    assert outcome is Outcome.BLOCKED
    assert part["observations"]["cleanup_needed"] == [p01.DELETE_LEDGER_NOTE]


async def test_auto_operator_runs_probe_1_and_leaves_company_a_as_it_was(tmp_path):
    books = FakeBooks(name=A)
    op = build_auto_operator(config=tmp_config(tmp_path), transport=books.transport(),
                             runner=FakeRunner(books, [TallyProcess(8, OWN_COMMAND)]), echo=lambda line: None)
    store = ResultsStore(tmp_path / "r.json")
    mark_done(store, 0)
    outcome = await run_probe(p01.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                              capture=Capture(tmp_path / "fixtures"), io=op)
    part = store.probe_entry(1)["parts"]["A"]
    assert outcome is Outcome.CONFIRMED, part["summary"]
    assert part["observations"]["run_mode"] == "auto"
    assert part["observations"]["ledger"] == "Electricity"
    assert books.state["ledgers"] == seed_state(A)["ledgers"]     # nothing left behind: no leftover EMAIL, no ledger
    assert books.state["vouchers"] == {}
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p01_company_counters.py -q`
Expected: FAIL — `AttributeError: module 'v2.probes.p01_company_counters' has no attribute 'EMAILS'` (and the
matrix / actions assertions fail).

- [x] **Step 3: Replace `v2/probes/p01_company_counters.py`**

```python
"""Probe 1 — which company counters move on which change (S0 spec §7 "Probe 1", §5.8 "Probe 1 revision").

Master steps run on a throwaway ledger (create → alter → alter again → delete), so company A is left as it was:
an empty-value alter is silently ignored by Tally (live 2026-09-22), so "clear the field again" can't be the revert.
In manual runs a person makes the changes at the Tally UI (S0-D3); in auto runs the operator makes them via XML (S0-D9).
"""
from __future__ import annotations

from v2.agent.tally.envelopes import formula_string, wrap_collection
from v2.agent.tally.xml_utils import read_objects
from v2.probes.actions import Action
from v2.probes.companies import THROWAWAY_DATE_TEXT
from v2.probes.context import ProbeContext, select_company
from v2.probes.core import Outcome, PartResult, Probe

CANDIDATE_FIELDS = ["GUID", "AltVchId", "AltMstId", "BooksFrom", "LastVoucherDate", "AlterID"]
COUNTERS_REQUEST = wrap_collection("S0CompanyCounters", "Company", ["Name", *CANDIDATE_FIELDS])
WATCHED = ["AltVchId", "AltMstId", "LastVoucherDate"]
THROWAWAY_LEDGER = "S0 Probe Ledger"
THROWAWAY_PARENT = "Indirect Expenses"
VOUCHER_REF = "p01-v1"
NARRATION = "S0-throwaway 1"
ALTERED_NARRATION = "S0-throwaway 1 (altered)"
EMAILS = ("s0probe-1@example.com", "s0probe-2@example.com")

DELETE_VOUCHER_NOTE = f"Delete the voucher with narration {NARRATION!r} (or {ALTERED_NARRATION!r}) if it still exists"
DELETE_LEDGER_NOTE = f"Delete ledger '{THROWAWAY_LEDGER}' if it exists"


def actions_for(company: str, ledger: str) -> list[tuple[str, str, str, Action]]:
    """(step, kind, instruction for a person, Action for the operator) in run order."""
    return [
        ("create_voucher", "voucher",
         f"Create a Payment voucher dated {THROWAWAY_DATE_TEXT}: Cash → {ledger}, ₹1, narration {NARRATION!r}. Save it.",
         Action("create_voucher", {"company": company, "ref": VOUCHER_REF, "ledger": ledger, "amount": "1.00",
                                   "narration": NARRATION})),
        ("alter_voucher", "voucher", f"Alter that voucher's narration to {ALTERED_NARRATION!r} and save.",
         Action("alter_voucher", {"company": company, "ref": VOUCHER_REF, "narration": ALTERED_NARRATION})),
        ("delete_voucher", "voucher", "Delete that voucher (open it, Alt+D).",
         Action("delete_voucher", {"company": company, "ref": VOUCHER_REF})),
        ("create_ledger", "master", f"Create a ledger {THROWAWAY_LEDGER!r} under {THROWAWAY_PARENT}.",
         Action("create_ledger", {"company": company, "name": THROWAWAY_LEDGER, "parent": THROWAWAY_PARENT})),
        ("alter_ledger", "master", f"Alter ledger {THROWAWAY_LEDGER!r}: set its E-Mail to {EMAILS[0]!r} and save.",
         Action("alter_ledger", {"company": company, "name": THROWAWAY_LEDGER, "email": EMAILS[0]})),
        ("alter_ledger_again", "master",
         f"Alter ledger {THROWAWAY_LEDGER!r} again: set its E-Mail to {EMAILS[1]!r} and save.",
         Action("alter_ledger", {"company": company, "name": THROWAWAY_LEDGER, "email": EMAILS[1]})),
        ("delete_ledger", "master", f"Delete ledger {THROWAWAY_LEDGER!r}.",
         Action("delete_ledger", {"company": company, "name": THROWAWAY_LEDGER})),
    ]


async def _pick_expense_ledger(ctx: ProbeContext) -> str:
    text = await ctx.send("ledger_list", wrap_collection("S0LedgerList", "Ledger", ["Name", "Parent"], ctx.company_name))
    rows = read_objects(text, "LEDGER", ["Name", "Parent"])
    if any(row["Name"] == "Bank Charges" for row in rows):
        return "Bank Charges"
    for row in rows:
        if row["Parent"] == "Indirect Expenses":
            return row["Name"]
    return ctx.ask("Type the name of an expense ledger in this company to use for the ₹1 test voucher:",
                   Action("expense_ledger"))


async def _ledger_alterid(ctx: ProbeContext, ledger: str, step: str) -> str:
    xml = wrap_collection("S0OneLedger", "Ledger", ["Name", "GUID", "AlterID"], ctx.company_name,
                          filters=[("S0OnlyLedger", f"$Name = {formula_string(ledger)}")])
    rows = read_objects(await ctx.send(step, xml), "LEDGER", ["Name", "AlterID"])
    return rows[0]["AlterID"] if rows else ""


async def run_a(ctx: ProbeContext) -> PartResult:
    row = select_company(await ctx.send("counters_candidates", COUNTERS_REQUEST), ctx.company_name, CANDIDATE_FIELDS)
    present = [field for field in CANDIDATE_FIELDS if row.get(field)]
    ctx.observe("fields_present", present)
    if not {"AltVchId", "AltMstId"} <= set(present):
        return PartResult(Outcome.FAILED, f"The Company collection doesn't expose AltVchId/AltMstId (got {present})",
                          spec_impact="No company-level change counters over XML: decision 9 falls back to a rolling "
                                      "re-pull of recent months + the daily GUID/AlterID compare (Part 1 R6).")
    ctx.confirm_request("company_counters", COUNTERS_REQUEST, fields=present)

    ledger = await _pick_expense_ledger(ctx)
    ctx.observe("ledger", ledger)
    if await _ledger_alterid(ctx, THROWAWAY_LEDGER, "throwaway_ledger_check"):
        return PartResult(Outcome.BLOCKED, f"Ledger {THROWAWAY_LEDGER!r} already exists (an earlier run?). Delete it in "
                          "Tally or run `uv run --project v2 python -m v2.probes reset-a`, then re-run — a duplicate "
                          "create freezes Tally (LESSONS §15 rule 10).")
    previous = await ctx.counters("counters_baseline")
    ledger_before = await _ledger_alterid(ctx, ledger, "ledger_before")
    ledger_after_voucher = ledger_before
    matrix: dict[str, dict] = {}
    for step, kind, instruction, action in actions_for(ctx.company_name, ledger):
        if step == "create_voucher":
            ctx.on_abort(DELETE_VOUCHER_NOTE)
        elif step == "create_ledger":
            ctx.on_abort(DELETE_LEDGER_NOTE)

        ctx.pause(f"{instruction} (company: {ctx.company_name!r})", action)
        current = await ctx.counters(f"counters_after_{step}")
        watched = [field for field in WATCHED if field in present]
        matrix[step] = {
            "kind": kind,
            "moved": {field: current.get(field) != previous.get(field) for field in watched},
            "values": {field: current.get(field) for field in watched},
        }
        if step == "create_voucher":
            ledger_after_voucher = await _ledger_alterid(ctx, ledger, "ledger_after_voucher")
        previous = current

        if step == "delete_voucher":
            ctx.resolve_abort(DELETE_VOUCHER_NOTE)
        elif step == "delete_ledger":
            ctx.resolve_abort(DELETE_LEDGER_NOTE)
    ctx.observe("matrix", matrix)
    ledger_moved = ledger_before != ledger_after_voucher
    ctx.observe("ledger_alterid_moved_on_voucher_entry", ledger_moved)

    deviations = []
    for step, entry in matrix.items():
        field = "AltVchId" if entry["kind"] == "voucher" else "AltMstId"
        if not entry["moved"].get(field):
            deviations.append(f"{field} did not move on {step}")
    if ledger_moved:
        deviations.append("entering a voucher moved the ledger's own AlterID")
    if deviations:
        return PartResult(Outcome.DIFFERENT, "; ".join(deviations),
                          spec_impact="Part 1 §4 change detection gets this matrix; decision 9 adds a rolling re-pull "
                                      "fallback for the changes that move no counter (R6), and 'Why the re-read' is "
                                      "revisited if a voucher entry moves the ledger's AlterID.")
    return PartResult(Outcome.CONFIRMED, "AltVchId moves on every voucher change, AltMstId on every master change; "
                                         "a voucher entry doesn't move the ledger's AlterID")


PROBE = Probe(
    id=1,
    name="company_counters",
    question="Which company counters (AltVchId, AltMstId, LastVoucherDate, a ledger's AlterID) move on which change?",
    feeds=("decision 9", "R6"),
    parts={"A": run_a},
    requires=(0,),
    mutating=True,
    educational_sensitive=True,
)
```

- [x] **Step 4: Run all v2 tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 72** (`test_p01_company_counters.py` now 11 tests instead of 8).

---
### Task 6: Shared read helpers + probe 16 (ledger closing balances, A part)

**Files:**
- Create: `v2/probes/reads.py`, `v2/probes/p16_ledger_closing_balance.py`
- Modify: `v2/probes/registry.py` (probe 16 `module=`), `v2/tests/probes/fakes.py` (voucher / stock builders, `a_tally`,
  `ready_store`)
- Test: `v2/tests/probes/test_reads.py`, `v2/tests/probes/test_p16_ledger_closing_balance.py`

**Interfaces:**
- Consumes: `wrap_collection`, `wrap_report`, `parse_ledger_list`, `parse_trial_balance`, `parse_stock_summary`,
  `parse_decimal`, `AmountParseError`, `read_objects`, `sanitize_xml`, `SEED_RECEIVABLE`, `SEED_PAYABLE`,
  `THROWAWAY_DATE_TEXT`, `THROWAWAY_EXPENSE_LEDGER`, `Action`
- Produces:
  - `reads`: `A_FY_FROM = "01-04-2025"`, `A_FY_TO = "31-03-2026"`, `VOUCHER_CHILDOF`, `ZERO`, `PRIMARY_NATURE`,
    `PL_PRIMARY_GROUPS`, `POSTING_RULES`, `voucher_request(name, fields, company, *, from_date, to_date, filters=None,
    extra_collection_xml="")`, `master_request(name, object_type, fields, company, *, static_vars=None, filters=None)`,
    `amount(text)`, `tally_date(text)`, `dmy(text)`, `qty_number(text)`, `signed_ui_amount(text)`,
    `parse_vouchers(raw) -> list[dict]` (`attrs`, `header`, `ledger_lines[{list, fields, amount, amount_raw, bills}]`,
    `inventory[{fields, accounting, batches}]`), `primary_lines(v)`, `postings(v, rule="default")`, `is_countable(v)`,
    `ledger_movements(vouchers, *, up_to=None, before=None, include_post_dated=False)`, `parse_parents(raw, tag="GROUP")`,
    `ancestors(name, parents)`, `top_group(group, parents)`, `stock_bearing_groups(parents)`, `tb_rows_any_depth(raw)`,
    `stock_rows_any_depth(raw)`
  - `p16_ledger_closing_balance`: `PROBE` (id 16, parts {"A"}, `planned_parts=("A", "B")`, `requires=(0, 1, 2)`,
    mutating, educational-sensitive), `UI_LEDGERS`, `FUTURE_REF`, `POST_DATED_REF`, `FUTURE_NARRATION`,
    `POST_DATED_NARRATION`, `FAILED_IMPACT`
  - fakes: `vch(header, lines=(), inventory=(), *, list_tag="ALLLEDGERENTRIES.LIST")`, `line(ledger, amount, **extra)`,
    `vouchers_xml(vouchers)`, `stock_summary_xml(items)`, `a_tally(state=None) -> (FakeTally, state)`,
    `ready_store(store, *, baseline=None, licence="licensed")`

**Probe 16 (A) — what it does** (spec §7 steps 1–8):
1. `ledgers` — Ledger collection Name, Parent, GUID, OpeningBalance, ClosingBalance. Extra steps: `groups` (group tree),
   `vouchers_fy` (FY vouchers with lines), `tb_fy_end` (fresh TB), `stock_summary_fy_end` (closing stock value).
2. Nominal ledgers (group nature income/expenses): ClosingBalance zero / empty / non-zero recorded.
3. Balance-sheet ledgers rolled up to their primary group vs the TB rows; a mismatch on the stock-bearing group that
   equals the Stock Summary total is recorded as "explained by stock".
4. Σ debtors vs ₹9,70,537; Σ creditors vs ₹18,34,142.
5. Ask (`ui_closing_balance`) for Apex Technologies Pvt Ltd, HP India Sales Pvt Ltd, HDFC Bank - Current A/c — typed
   "62,800.00 Dr" style; empty = not read (auto mode always answers empty → a later manual check).
6. Per balance-sheet ledger: ClosingBalance = OpeningBalance + Σ lines (countable vouchers to FY end).
7. As-on: `ledgers_asof_2025-10-31` (SVFROMDATE 01-04-2025, SVTODATE 31-10-2025) and `ledgers_from_2025-10-01`
   (01-10-2025 … 31-10-2025) vs opening + Σ lines to / before those dates.
8. Throwaway vouchers on Cash → Electricity dated 31-Mar-2026 (after Tally's current date 1-Mar-2026): first an
   ordinary one (extra steps `future_voucher`, `ledgers_with_future_voucher` — settles "ClosingBalance as of the F2 date
   or the period end", which seed data alone can't: its last voucher is dated the F2 date), then a post-dated one
   (`post_dated_voucher`, `ledgers_with_post_dated`); each deleted straight after, with a cleanup note in between.

Outcome rules: **FAILED** if any balance-sheet ledger's ClosingBalance ≠ opening + Σ lines, or Σ debtors / creditors ≠
the anchors, or a typed UI balance differs (spec impact `FAILED_IMPACT` + the rung-1 rule). **DIFFERENT** if a nominal
ledger has a non-zero ClosingBalance, or a TB group row ≠ the ledger rollup (explained-by-stock or not; each gets its
own spec-impact sentence). **CONFIRMED** otherwise. Every outcome's `spec_impact` carries the rung-1 rule sentence
(as-of date, post-dated rule, IsPostDated export) and the as-on sentence (decision 11 anchors). **BLOCKED** if the ledger
collection is empty.

- [x] **Step 1: Add builders to `v2/tests/probes/fakes.py`** (append):

```python
COMPANY_A = "Bharat Traders Probe Copy"


def _leafs(fields: dict) -> str:
    return "".join(f"<{k}>{esc(str(v))}</{k}>" for k, v in fields.items()
                   if not k.startswith("_") and not isinstance(v, (list, tuple)))


def line(ledger: str, amount: str, **extra) -> dict:
    """A ledger line; ISDEEMEDPOSITIVE follows the sign (debit negative, Part 1 §6). extra: bills=[…], _list=tag."""
    return {"LEDGERNAME": ledger, "ISDEEMEDPOSITIVE": "Yes" if amount.startswith("-") else "No", "AMOUNT": amount,
            **extra}


def vch(header: dict[str, str], lines=(), inventory=(), *, list_tag: str = "ALLLEDGERENTRIES.LIST") -> str:
    """One <VOUCHER> the way Tally exports it, including the empty placeholder lists it always adds."""
    body = _leafs(header)
    for item in lines:
        tag = item.get("_list", list_tag)
        bills = "".join(f"<BILLALLOCATIONS.LIST>{_leafs(b)}</BILLALLOCATIONS.LIST>" for b in item.get("bills", ()))
        body += f"<{tag}>{_leafs(item)}{bills or '<BILLALLOCATIONS.LIST>  </BILLALLOCATIONS.LIST>'}</{tag}>"
    for inv in inventory:
        accounting = "".join(f"<ACCOUNTINGALLOCATIONS.LIST>{_leafs(a)}</ACCOUNTINGALLOCATIONS.LIST>"
                             for a in inv.get("accounting", ()))
        batches = "".join(f"<BATCHALLOCATIONS.LIST>{_leafs(b)}</BATCHALLOCATIONS.LIST>" for b in inv.get("batches", ()))
        body += f"<ALLINVENTORYENTRIES.LIST>{_leafs(inv)}{accounting}{batches}</ALLINVENTORYENTRIES.LIST>"
    kind = esc(header.get("VOUCHERTYPENAME", "Payment"))
    return f'<VOUCHER VCHTYPE="{kind}">{body}<INVOICEORDERLIST.LIST>  </INVOICEORDERLIST.LIST></VOUCHER>'


def vouchers_xml(vouchers: list[str]) -> str:
    """A voucher collection response, with CMPINFO's <VOUCHER>0</VOUCHER> counter that parsers must skip."""
    return ("<ENVELOPE><BODY><DESC><CMPINFO><VOUCHER>0</VOUCHER></CMPINFO></DESC><DATA><COLLECTION>"
            + "".join(vouchers) + "</COLLECTION></DATA></BODY></ENVELOPE>")


def stock_summary_xml(items: list[tuple[str, str, str, str]]) -> str:
    """items: (name, closing qty text e.g. '45 Nos', rate text, value text)."""
    return "<ENVELOPE>" + "".join(
        f"<DSPACCNAME><DSPDISPNAME>{esc(name)}</DSPDISPNAME></DSPACCNAME><DSPSTKINFO><DSPSTKCL>"
        f"<DSPCLQTY>{qty}</DSPCLQTY><DSPCLRATE>{rate}</DSPCLRATE><DSPCLAMTA>{value}</DSPCLAMTA></DSPSTKCL></DSPSTKINFO>"
        for name, qty, rate, value in items) + "</ENVELOPE>"


def a_tally(state: dict | None = None) -> tuple["FakeTally", dict]:
    """FakeTally with company A open and a counters route driven by `state` (AltVchId, AltMstId, optional GUID)."""
    state = state if state is not None else {"AltVchId": 50, "AltMstId": 266}
    fake = FakeTally([COMPANY_A])
    fake.route("S0CompanyCounters", lambda body: objects_xml("COMPANY", [{
        "Name": COMPANY_A, "GUID": state.get("GUID", "g-1"), "AltVchId": str(state["AltVchId"]),
        "AltMstId": str(state["AltMstId"]), "BooksFrom": "20250401", "LastVoucherDate": "20260301",
        "AlterID": str(state["AltMstId"])}]))
    return fake, state


def ready_store(store: ResultsStore, *, baseline: dict[str, str] | None = None, licence: str = "licensed") -> None:
    """Probes 0, 1, 2 done, counters confirmed with probe 1's request, environment as probe 0 leaves it."""
    from v2.probes.p01_company_counters import CANDIDATE_FIELDS, COUNTERS_REQUEST
    for probe_id in (0, 1, 2):
        mark_done(store, probe_id)
    store.confirm_request("company_counters", 1, COUNTERS_REQUEST, fields=list(CANDIDATE_FIELDS))
    store.update_environment(licence=licence, company_a_tb_baseline=baseline or {})
```

- [x] **Step 2: Write the failing tests**

`v2/tests/probes/test_reads.py`:
```python
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
```

`v2/tests/probes/test_p16_ledger_closing_balance.py`:
```python
from decimal import Decimal

import httpx

from v2.probes import p16_ledger_closing_balance as p16
from v2.probes.core import Outcome
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import (ScriptedIO, a_tally, line, make_harness, objects_xml, ready_store,
                                   stock_summary_xml, tb_xml, vch, vouchers_xml)

APEX, HP = "Apex Technologies Pvt Ltd", "HP India Sales Pvt Ltd"
GROUPS = [
    {"Name": "Current Assets", "Parent": "Primary"}, {"Name": "Sundry Debtors", "Parent": "Current Assets"},
    {"Name": "North Zone Debtors", "Parent": "Sundry Debtors"}, {"Name": "Cash-in-Hand", "Parent": "Current Assets"},
    {"Name": "Stock-in-Hand", "Parent": "Current Assets"}, {"Name": "Current Liabilities", "Parent": "Primary"},
    {"Name": "Sundry Creditors", "Parent": "Current Liabilities"},
    {"Name": "National Creditors", "Parent": "Sundry Creditors"}, {"Name": "Capital Account", "Parent": "Primary"},
    {"Name": "Sales Accounts", "Parent": "Primary"}, {"Name": "Purchase Accounts", "Parent": "Primary"},
    {"Name": "Indirect Expenses", "Parent": "Primary"},
]
VOUCHERS = vouchers_xml([
    vch({"DATE": "20251015", "VOUCHERTYPENAME": "Sales"}, lines=[line(APEX, "-970537.00"), line("Sales", "970537.00")]),
    vch({"DATE": "20250910", "VOUCHERTYPENAME": "Purchase"},
        lines=[line(HP, "1834142.00"), line("Purchases", "-1834142.00")]),
    vch({"DATE": "20251105", "VOUCHERTYPENAME": "Payment"}, lines=[line("Electricity", "-100.00"), line("Cash", "100.00")]),
])
TB = tb_xml([("Capital Account", "", "1000.00"), ("Current Liabilities", "", "1834142.00"),
             ("Current Assets", "-971437.00", ""), ("Sales Accounts", "", "970537.00"),
             ("Purchase Accounts", "-1834142.00", ""), ("Indirect Expenses", "-100.00", "")])
TB_WITH_STOCK = tb_xml([("Capital Account", "", "1000.00"), ("Current Liabilities", "", "1834142.00"),
                        ("Current Assets", "-976437.00", ""), ("Sales Accounts", "", "970537.00"),
                        ("Purchase Accounts", "-1834142.00", ""), ("Indirect Expenses", "-100.00", "")])


def _ledger(name, parent, opening="", closing=""):
    return {"Name": name, "Parent": parent, "OpeningBalance": opening, "ClosingBalance": closing}


ASOF = [_ledger(APEX, "North Zone Debtors", closing="-970537.00"), _ledger(HP, "National Creditors", closing="1834142.00"),
        _ledger("Cash", "Cash-in-Hand", "-1000.00", "-1000.00"), _ledger("Capital Account", "Capital Account", "1000.00", "1000.00")]
FROM = [_ledger(APEX, "North Zone Debtors", "", "-970537.00"), _ledger(HP, "National Creditors", "1834142.00", "1834142.00"),
        _ledger("Cash", "Cash-in-Hand", "-1000.00", "-1000.00"), _ledger("Capital Account", "Capital Account", "1000.00", "1000.00")]


def _fy_ledgers(state):
    cash = Decimal("-900.00") + (1 if state["future"] else 0) + (1 if state["post_dated"] and state["pd_counts"] else 0)
    return [
        _ledger(APEX, "North Zone Debtors", closing="-970537.00"),
        _ledger(HP, "National Creditors", closing="1834142.00"),
        _ledger("Cash", "Cash-in-Hand", "-1000.00", state.get("cash_override") or f"{cash:.2f}"),
        _ledger("Capital Account", "Capital Account", "1000.00", "1000.00"),
        _ledger("Sales", "Sales Accounts"), _ledger("Purchases", "Purchase Accounts"),
        _ledger("Electricity", "Indirect Expenses", closing=state.get("electricity", "")),
        _ledger("Profit & Loss A/c", "Primary"),
    ]


def _fake(**overrides):
    state = {"future": False, "post_dated": False, "pd_counts": False, "as_on": True, "tb": TB, "stock": "0.00",
             **overrides}
    fake, _ = a_tally()

    def ledgers(body):
        if state["as_on"] and "<SVTODATE>31-10-2025</SVTODATE>" in body:
            return objects_xml("LEDGER", FROM if "<SVFROMDATE>01-10-2025</SVFROMDATE>" in body else ASOF)
        return objects_xml("LEDGER", _fy_ledgers(state))

    def throwaways(body):
        rows = []
        if state["future"]:
            rows.append(vch({"DATE": "20260331", "NARRATION": p16.FUTURE_NARRATION, "ISPOSTDATED": "No", "MASTERID": "51"}))
        if state["post_dated"]:
            rows.append(vch({"DATE": "20260331", "NARRATION": p16.POST_DATED_NARRATION, "ISPOSTDATED": "Yes",
                             "MASTERID": "52"}))
        return vouchers_xml(rows)

    fake.route("S0P16Ledgers", ledgers)
    fake.route("S0P16Groups", lambda body: objects_xml("GROUP", GROUPS))
    fake.route("S0P16Vouchers", lambda body: VOUCHERS)
    fake.route("S0P16Throwaway", throwaways)
    fake.route("<ID>Trial Balance</ID>", lambda body: state["tb"])
    fake.route("<ID>Stock Summary</ID>", lambda body: stock_summary_xml([("Electronics", "60 Nos", "", state["stock"])]))

    def on_action(action):
        key = "future" if action.params["ref"] == p16.FUTURE_REF else "post_dated"
        state[key] = action.kind == "create_voucher"

    return fake, on_action


def _io(on_action, answers=None):
    return ScriptedIO(on_action=on_action, answers=answers,
                      answers_by_kind=None if answers else {"ui_closing_balance": ""})


async def _run(tmp_path, fake, io):
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    outcome = await run_probe(p16.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return outcome, store, store.probe_entry(16)["parts"]["A"]


async def test_confirmed_path_records_the_rung1_rule(tmp_path):
    fake, on_action = _fake()
    io = _io(on_action)
    outcome, store, part = await _run(tmp_path, fake, io)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert outcome is Outcome.PARTIAL and store.probe_entry(16)["remaining"] == ["B"]
    obs = part["observations"]
    assert obs["as_on"]["closing_follows_svtodate"] is True and obs["as_on"]["opening_follows_svfromdate"] is True
    assert obs["future_voucher"]["included_in_closing"] is True
    assert obs["post_dated_voucher"]["included_in_closing"] is False
    assert obs["post_dated_voucher"]["is_post_dated_exported"] == "Yes"
    assert "the period end" in part["spec_impact"] and "post-dated vouchers are excluded" in part["spec_impact"]
    assert "UI balances not read" in part["summary"]
    assert [a.kind for a in io.actions] == ["create_voucher", "delete_voucher", "create_voucher", "delete_voucher"]
    assert io.actions[2].params["post_dated"] is True
    assert part["fixtures"] == [
        "p16_A_ledgers.xml", "p16_A_groups.xml", "p16_A_vouchers_fy.xml", "p16_A_tb_fy_end.xml",
        "p16_A_stock_summary_fy_end.xml", "p16_A_ledgers_asof_2025-10-31.xml", "p16_A_ledgers_from_2025-10-01.xml",
        "p16_A_future_voucher.xml", "p16_A_ledgers_with_future_voucher.xml", "p16_A_post_dated_voucher.xml",
        "p16_A_ledgers_with_post_dated.xml",
    ]


async def test_closing_not_matching_lines_fails(tmp_path):
    fake, on_action = _fake(cash_override="-800.00")
    outcome, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "FAILED"
    assert "Cash" in part["summary"] and "rung 1 collapses" in part["spec_impact"]


async def test_ui_balance_mismatch_fails(tmp_path):
    fake, on_action = _fake()
    _, _, part = await _run(tmp_path, fake, _io(on_action, answers=["1.00 Dr", "", ""]))
    assert part["outcome"] == "FAILED"
    assert "Tally UI shows another balance for Apex Technologies Pvt Ltd" in part["summary"]


async def test_tb_row_explained_by_closing_stock_is_different(tmp_path):
    fake, on_action = _fake(tb=TB_WITH_STOCK, stock="5000.00")
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "DIFFERENT"
    assert part["observations"]["tb_vs_rollup"]["Current Assets"]["explained_by_stock"] is True
    assert "Stock Summary" in part["spec_impact"]


async def test_nonzero_nominal_ledger_is_different(tmp_path):
    fake, on_action = _fake(electricity="-100.00")
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "DIFFERENT"
    assert "nominal ledger(s)" in part["summary"]
    assert part["observations"]["nominal"]["nonzero"] == {"Electricity": Decimal("-100.00")}   # in memory: Decimal


async def test_as_on_ignored_is_recorded_not_failed(tmp_path):
    fake, on_action = _fake(as_on=False)
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["as_on"]["closing_follows_svtodate"] is False
    assert "depend on probe 17" in part["spec_impact"]


async def test_throwaway_voucher_has_a_cleanup_note_until_deleted(tmp_path):
    fake, on_action = _fake()
    fake.routes = [(m, h) for m, h in fake.routes if m != "S0P16Throwaway"]
    fake.route("S0P16Throwaway", lambda body: httpx.ReadTimeout)
    _, _, part = await _run(tmp_path, fake, _io(on_action))
    assert part["outcome"] == "BLOCKED"
    assert part["observations"]["cleanup_needed"] == [
        f"Delete the voucher with narration {p16.FUTURE_NARRATION!r} if it still exists"]
```

- [x] **Step 3: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_reads.py v2/tests/probes/test_p16_ledger_closing_balance.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.reads'`.

- [x] **Step 4: Write `v2/probes/reads.py`**

```python
"""Read requests and parsers shared by the company-A probes (probe side only; S2 grows its own in v2/agent/tally/)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal

from v2.agent.tally.amounts import AmountParseError, parse_decimal
from v2.agent.tally.envelopes import wrap_collection
from v2.agent.tally.xml_utils import read_objects, sanitize_xml

A_FY_FROM = "01-04-2025"
A_FY_TO = "31-03-2026"
VOUCHER_CHILDOF = "<CHILDOF>$$VchTypeAllVouchers</CHILDOF>"    # without it a Voucher collection has empty bodies (v4)
LEDGER_LISTS = ("ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST")
INVENTORY_LISTS = ("ALLINVENTORYENTRIES.LIST", "INVENTORYENTRIES.LIST")
POSTING_RULES = ("default", "all_only", "ledger_plus_alloc", "all_plus_alloc")
ZERO = Decimal("0")

# Tally's reserved primary groups and the nature S1 gives each (Part 1 §6 rung 1 needs balance-sheet vs P&L).
PRIMARY_NATURE: dict[str, str] = {
    "Capital Account": "liabilities", "Loans (Liability)": "liabilities", "Current Liabilities": "liabilities",
    "Suspense A/c": "liabilities", "Branch / Divisions": "liabilities",
    "Fixed Assets": "assets", "Investments": "assets", "Current Assets": "assets", "Misc. Expenses (ASSET)": "assets",
    "Sales Accounts": "income", "Direct Incomes": "income", "Indirect Incomes": "income",
    "Purchase Accounts": "expenses", "Direct Expenses": "expenses", "Indirect Expenses": "expenses",
}
PL_PRIMARY_GROUPS = frozenset(group for group, nature in PRIMARY_NATURE.items() if nature in ("income", "expenses"))


# --- requests -------------------------------------------------------------------------------------------------------
def voucher_request(name: str, fields: list[str], company: str, *, from_date: str = A_FY_FROM, to_date: str = A_FY_TO,
                    filters: list[tuple[str, str]] | None = None, extra_collection_xml: str = "") -> str:
    return wrap_collection(name, "Voucher", fields, company, static_vars={"SVFROMDATE": from_date, "SVTODATE": to_date},
                           filters=filters, extra_collection_xml=VOUCHER_CHILDOF + extra_collection_xml)


def master_request(name: str, object_type: str, fields: list[str], company: str, *,
                   static_vars: dict[str, str] | None = None, filters: list[tuple[str, str]] | None = None) -> str:
    return wrap_collection(name, object_type, fields, company, static_vars=static_vars, filters=filters)


# --- values ---------------------------------------------------------------------------------------------------------
def amount(text: str | None) -> Decimal | None:
    """parse_decimal, except that a non-plain amount (e.g. a forex expression) reads as None instead of raising."""
    try:
        return parse_decimal(text)
    except AmountParseError:
        return None


def tally_date(text: str) -> date | None:
    """'20251001', '1-Oct-25', '01-Oct-2025' or '01-10-2025' → a date; anything else → None."""
    cleaned = (text or "").strip()
    for fmt in ("%Y%m%d", "%d-%b-%y", "%d-%b-%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def dmy(text: str) -> date:
    return datetime.strptime(text, "%d-%m-%Y").date()


def qty_number(text: str) -> Decimal | None:
    """' 25 Nos' → 25; '-2.0000 NOS' → -2; '' → None."""
    parts = (text or "").strip().split()
    return amount(parts[0]) if parts else None


def signed_ui_amount(text: str) -> Decimal | None:
    """A balance typed from the Tally UI: '62,800 Dr' → -62800 (debit negative); '1,000 Cr' → 1000; '' → None."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if lowered.endswith(("dr", "cr")):
        value = amount(cleaned[:-2])
        if value is None:
            return None
        return -abs(value) if lowered.endswith("dr") else abs(value)
    return amount(cleaned)


# --- vouchers -------------------------------------------------------------------------------------------------------
def _leaf_fields(element: ET.Element) -> dict[str, str]:
    return {child.tag: (child.text or "").strip() for child in element if len(child) == 0}


def _filled(element: ET.Element, tag: str) -> list[ET.Element]:
    """Direct children named `tag` that hold something (Tally also exports empty placeholder lists)."""
    return [child for child in element if child.tag == tag and len(child) > 0]


def _line(element: ET.Element, list_tag: str) -> dict:
    fields = _leaf_fields(element)
    return {"list": list_tag, "fields": fields, "amount": amount(fields.get("AMOUNT")),
            "amount_raw": fields.get("AMOUNT", ""),
            "bills": [_leaf_fields(bill) for bill in _filled(element, "BILLALLOCATIONS.LIST")]}


def parse_vouchers(raw_xml: str) -> list[dict]:
    root = ET.fromstring(sanitize_xml(raw_xml))
    vouchers: list[dict] = []
    for element in root.iter("VOUCHER"):
        if len(element) == 0:
            continue                                   # CMPINFO's <VOUCHER>0</VOUCHER> counter
        lines = [_line(child, tag) for tag in LEDGER_LISTS for child in _filled(element, tag)]
        inventory = [{"fields": _leaf_fields(inv),
                      "accounting": [_line(a, "ACCOUNTINGALLOCATIONS.LIST")
                                     for a in _filled(inv, "ACCOUNTINGALLOCATIONS.LIST")],
                      "batches": [_leaf_fields(b) for b in _filled(inv, "BATCHALLOCATIONS.LIST")]}
                     for tag in INVENTORY_LISTS for inv in _filled(element, tag)]
        vouchers.append({"attrs": dict(element.attrib), "header": _leaf_fields(element), "ledger_lines": lines,
                         "inventory": inventory})
    return vouchers


def primary_lines(voucher: dict) -> list[dict]:
    """The voucher's own ledger lines: ALLLEDGERENTRIES.LIST if it has any, else LEDGERENTRIES.LIST — never both."""
    all_lines = [item for item in voucher["ledger_lines"] if item["list"] == "ALLLEDGERENTRIES.LIST"]
    return all_lines or [item for item in voucher["ledger_lines"] if item["list"] == "LEDGERENTRIES.LIST"]


def postings(voucher: dict, rule: str = "default") -> list[tuple[str, Decimal | None]]:
    """(ledger, amount) per posting. 'default' = primary lines + inventory accounting allocations (probe 6 checks it)."""
    all_lines = [item for item in voucher["ledger_lines"] if item["list"] == "ALLLEDGERENTRIES.LIST"]
    ledger_lines = [item for item in voucher["ledger_lines"] if item["list"] == "LEDGERENTRIES.LIST"]
    allocations = [a for inv in voucher["inventory"] for a in inv["accounting"]]
    chosen = {"default": primary_lines(voucher) + allocations, "all_only": all_lines,
              "ledger_plus_alloc": ledger_lines + allocations, "all_plus_alloc": all_lines + allocations}[rule]
    return [(item["fields"].get("LEDGERNAME", ""), item["amount"]) for item in chosen]


def is_countable(voucher: dict) -> bool:
    """Affects balances: not cancelled, not optional (post-dated vouchers are the caller's choice)."""
    header = voucher["header"]
    return header.get("ISCANCELLED", "No") != "Yes" and header.get("ISOPTIONAL", "No") != "Yes"


def ledger_movements(vouchers: list[dict], *, up_to: date | None = None, before: date | None = None,
                     include_post_dated: bool = False) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for voucher in vouchers:
        if not is_countable(voucher):
            continue
        if not include_post_dated and voucher["header"].get("ISPOSTDATED", "No") == "Yes":
            continue
        when = tally_date(voucher["header"].get("DATE", ""))
        if when is None or (up_to is not None and when > up_to) or (before is not None and when >= before):
            continue
        for ledger, value in postings(voucher):
            if value is not None:
                totals[ledger] = totals.get(ledger, ZERO) + value
    return totals


# --- masters --------------------------------------------------------------------------------------------------------
def parse_parents(raw_xml: str, tag: str = "GROUP") -> dict[str, str]:
    """name → parent for every `tag` object (primary groups have parent '' or 'Primary')."""
    return {row["Name"]: row["Parent"] for row in read_objects(raw_xml, tag, ["Name", "Parent"]) if row["Name"]}


def _is_top(parent: str) -> bool:
    return parent in ("", "Primary")


def ancestors(name: str, parents: dict[str, str]) -> list[str]:
    """[name, parent, grandparent, …] up to the primary group (cycle-safe)."""
    chain = [name]
    while name in parents and not _is_top(parents[name]) and parents[name] not in chain:
        name = parents[name]
        chain.append(name)
    return chain


def top_group(group: str, parents: dict[str, str]) -> str:
    return ancestors(group, parents)[-1]


def stock_bearing_groups(parents: dict[str, str]) -> set[str]:
    """The primary group holding Stock-in-Hand, whose TB row may include closing stock (no ledger carries it)."""
    return {top_group("Stock-in-Hand", parents)} if "Stock-in-Hand" in parents else {"Current Assets"}


# --- report rows at any depth (exploded reports) ---------------------------------------------------------------------
def tb_rows_any_depth(raw_xml: str) -> list[dict]:
    """name, debit, credit, closing for every DSPDISPNAME in document order — flat or nested (exploded TBs)."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows: list[dict] = []
    current: dict | None = None
    for element in root.iter():
        if element.tag == "DSPDISPNAME":
            current = {"name": (element.text or "").strip(), "debit": None, "credit": None}
            rows.append(current)
        elif current is not None and element.tag == "DSPCLDRAMTA":
            current["debit"] = amount(element.text)
        elif current is not None and element.tag == "DSPCLCRAMTA":
            current["credit"] = amount(element.text)
    for row in rows:
        present = [value for value in (row["debit"], row["credit"]) if value is not None]
        row["closing"] = sum(present, ZERO) if present else None
    return rows


def stock_rows_any_depth(raw_xml: str) -> list[dict]:
    """name, qty text, closing qty and closing value for every DSPDISPNAME in a Stock Summary — flat or exploded."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows: list[dict] = []
    current: dict | None = None
    for element in root.iter():
        if element.tag == "DSPDISPNAME":
            current = {"name": (element.text or "").strip(), "qty_text": "", "qty": None, "value": None}
            rows.append(current)
        elif current is not None and element.tag == "DSPCLQTY":
            current["qty_text"] = (element.text or "").strip()
            current["qty"] = qty_number(current["qty_text"])
        elif current is not None and element.tag == "DSPCLAMTA":
            current["value"] = amount(element.text)
    return rows
```

- [x] **Step 5: Write `v2/probes/p16_ledger_closing_balance.py`**

```python
"""Probe 16 — does LEDGER.ClosingBalance hold Tally's own ledger balance? (S0 spec §7 "Probe 16", A part)

Feeds decision 11, R30 and Part 2 Rule 1 (Part 1 §6 rung 1). The B part (OpeningBalance scope, as-on 31-03-2023)
comes in plan part 3, so the probe stays PARTIAL until then.
"""
from __future__ import annotations

from decimal import Decimal

from v2.agent.tally.envelopes import wrap_report
from v2.agent.tally.reports import parse_ledger_list, parse_stock_summary, parse_trial_balance
from v2.probes.actions import Action
from v2.probes.anchors import SEED_PAYABLE, SEED_RECEIVABLE
from v2.probes.companies import THROWAWAY_DATE_TEXT, THROWAWAY_EXPENSE_LEDGER
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import (A_FY_FROM, A_FY_TO, PL_PRIMARY_GROUPS, ZERO, ancestors, dmy, ledger_movements,
                             master_request, parse_parents, parse_vouchers, signed_ui_amount, stock_bearing_groups,
                             top_group, voucher_request)

LEDGER_FIELDS = ["Name", "Parent", "GUID", "OpeningBalance", "ClosingBalance"]
VOUCHER_FIELDS = ["Date", "VoucherTypeName", "MasterId", "Narration", "IsCancelled", "IsOptional", "IsPostDated",
                  "AllLedgerEntries", "LedgerEntries", "AllInventoryEntries"]
THROWAWAY_FIELDS = ["Date", "MasterId", "Narration", "IsPostDated"]
UI_LEDGERS = ("Apex Technologies Pvt Ltd", "HP India Sales Pvt Ltd", "HDFC Bank - Current A/c")
AS_ON_FROM, AS_ON_TO = "01-10-2025", "31-10-2025"
CASH = "Cash"
FUTURE_REF, POST_DATED_REF = "p16-future", "p16-post-dated"
FUTURE_NARRATION = "S0-throwaway 16 future"
POST_DATED_NARRATION = "S0-throwaway 16 post-dated"
FAILED_IMPACT = ("LEDGER.ClosingBalance isn't Tally's ledger balance: rung 1 collapses to group level, month-bisect "
                 "becomes the main localiser, and Part 2 Rule 1 falls back to group-level forward computation "
                 "(decision 11, Part 1 §16).")


def _ledgers_request(company: str, static_vars: dict[str, str] | None = None) -> str:
    return master_request("S0P16Ledgers", "Ledger", LEDGER_FIELDS, company, static_vars=static_vars)


def _balances(text: str) -> dict[str, dict]:
    return {row["name"]: row for row in parse_ledger_list(text)}


def _value(value: Decimal | None) -> Decimal:
    return value if value is not None else ZERO


def _kinds(ledgers: dict[str, dict], groups: dict[str, str]) -> dict[str, str]:
    """ledger → 'bs' | 'pl' | 'special' (the Profit & Loss A/c sits directly under Primary)."""
    kinds: dict[str, str] = {}
    for name, row in ledgers.items():
        parent = row["parent_group"]
        if parent in ("", "Primary"):
            kinds[name] = "special"
        else:
            kinds[name] = "pl" if top_group(parent, groups) in PL_PRIMARY_GROUPS else "bs"
    return kinds


def _nominal(ledgers: dict[str, dict], kinds: dict[str, str]) -> dict:
    zero, empty, nonzero = [], [], {}
    for name, kind in sorted(kinds.items()):
        if kind != "pl":
            continue
        closing = ledgers[name]["closing_balance"]
        if closing is None:
            empty.append(name)
        elif closing == ZERO:
            zero.append(name)
        else:
            nonzero[name] = closing
    return {"zero": zero, "empty": empty, "nonzero": nonzero}


def _lines_check(ledgers: dict[str, dict], kinds: dict[str, str],
                 movements: dict[str, Decimal]) -> tuple[dict[str, dict], list[str]]:
    """Balance-sheet ledgers whose ClosingBalance ≠ OpeningBalance + Σ lines; and those exported empty for zero."""
    bad: dict[str, dict] = {}
    empty_for_zero: list[str] = []
    for name, kind in sorted(kinds.items()):
        if kind != "bs":
            continue
        closing = ledgers[name]["closing_balance"]
        computed = _value(ledgers[name]["opening_balance"]) + movements.get(name, ZERO)
        if closing is None and computed == ZERO:
            empty_for_zero.append(name)
        elif closing != computed:
            bad[name] = {"closing": closing, "computed": computed}
    return bad, empty_for_zero


def _group_compare(ledgers: dict[str, dict], kinds: dict[str, str], groups: dict[str, str],
                   tb_rows: dict[str, Decimal | None], stock_total: Decimal | None) -> dict[str, dict]:
    rollups: dict[str, Decimal] = {}
    for name, kind in kinds.items():
        if kind == "bs":
            top = top_group(ledgers[name]["parent_group"], groups)
            rollups[top] = rollups.get(top, ZERO) + _value(ledgers[name]["closing_balance"])
    stock_groups = stock_bearing_groups(groups)
    result: dict[str, dict] = {}
    for group in sorted(set(rollups) | {g for g in tb_rows if g not in PL_PRIMARY_GROUPS}):
        tb, rollup = tb_rows.get(group), rollups.get(group, ZERO)
        entry: dict = {"tb": tb, "rollup": rollup, "match": _value(tb) == rollup}
        if not entry["match"] and group in stock_groups and tb is not None and stock_total is not None:
            entry["stock_total"] = stock_total
            entry["explained_by_stock"] = abs(tb - rollup) == stock_total or abs(tb + rollup) == stock_total
        result[group] = entry
    return result


def _party_totals(ledgers: dict[str, dict], groups: dict[str, str]) -> tuple[Decimal, Decimal]:
    debtors = creditors = ZERO
    for row in ledgers.values():
        if row["parent_group"] in ("", "Primary"):
            continue
        chain = ancestors(row["parent_group"], groups)
        if "Sundry Debtors" in chain:
            debtors += _value(row["closing_balance"])
        elif "Sundry Creditors" in chain:
            creditors += _value(row["closing_balance"])
    return debtors, creditors


def _ui_compare(ctx: ProbeContext, ledgers: dict[str, dict]) -> dict[str, dict]:
    ui: dict[str, dict] = {}
    for name in UI_LEDGERS:
        typed = ctx.ask(f"In Tally, open ledger {name!r} (Display More Reports → Account Books → Ledger) and type the "
                        f"closing balance it shows, e.g. '62,800.00 Dr' — or press Enter to skip:",
                        Action("ui_closing_balance", {"ledger": name}))
        value = signed_ui_amount(typed)
        closing = ledgers.get(name, {}).get("closing_balance")
        ui[name] = {"typed": typed, "ui": value, "closing": closing,
                    "match": None if value is None else value == closing}
    return ui


async def _as_on(ctx: ProbeContext, ledgers: dict[str, dict], kinds: dict[str, str], vouchers: list[dict]) -> dict:
    company = ctx.company_name
    up_to = ledger_movements(vouchers, up_to=dmy(AS_ON_TO))
    before = ledger_movements(vouchers, before=dmy(AS_ON_FROM))
    as_of = _balances(await ctx.send("ledgers_asof_2025-10-31",
                                     _ledgers_request(company, {"SVFROMDATE": A_FY_FROM, "SVTODATE": AS_ON_TO})))
    ranged = _balances(await ctx.send("ledgers_from_2025-10-01",
                                      _ledgers_request(company, {"SVFROMDATE": AS_ON_FROM, "SVTODATE": AS_ON_TO})))
    bs = [name for name, kind in kinds.items() if kind == "bs"]

    def opening(name: str) -> Decimal:
        return _value(ledgers[name]["opening_balance"])

    closing_ok = all(_value(as_of.get(n, {}).get("closing_balance")) == opening(n) + up_to.get(n, ZERO) for n in bs)
    closing_changed = any(as_of.get(n, {}).get("closing_balance") != ledgers[n]["closing_balance"] for n in bs)
    opening_ok = all(_value(ranged.get(n, {}).get("opening_balance")) == opening(n) + before.get(n, ZERO) for n in bs)
    opening_changed = any(_value(ranged.get(n, {}).get("opening_balance")) != opening(n) for n in bs)
    return {"closing_follows_svtodate": closing_ok and closing_changed, "closing_matches_lines": closing_ok,
            "closing_changed": closing_changed, "opening_follows_svfromdate": opening_ok and opening_changed,
            "opening_matches_lines": opening_ok, "opening_changed": opening_changed}


def _as_on_note(as_on: dict) -> str:
    if as_on["opening_follows_svfromdate"]:
        return ("As-on works: OpeningBalance follows SVFROMDATE, so per-ledger opening anchors exist during the "
                "backfill without probe 17 (decision 11).")
    if as_on["closing_follows_svtodate"]:
        return ("As-on closing works (ClosingBalance follows SVTODATE) but OpeningBalance ignores SVFROMDATE: per-ledger "
                "anchors use the as-on closing of the day before the window (decision 11).")
    return ("As-on reading doesn't work (the period variables are ignored): per-ledger anchors during the backfill "
            "depend on probe 17 (decision 11).")


async def _throwaway(ctx: ProbeContext, *, ref: str, narration: str, post_dated: bool, step: str, ledger_step: str,
                     cash_before: Decimal | None) -> dict:
    company = ctx.company_name
    note = f"Delete the voucher with narration {narration!r} if it still exists"
    ctx.on_abort(note)
    kind = "marked post-dated (Ctrl+T on the voucher screen)" if post_dated else "an ordinary (not post-dated) voucher"
    ctx.pause(f"Create a Payment voucher dated {THROWAWAY_DATE_TEXT}, {kind}: Cash → {THROWAWAY_EXPENSE_LEDGER}, ₹1, "
              f"narration {narration!r}. Save it. (company: {company!r})",
              Action("create_voucher", {"company": company, "ref": ref, "ledger": THROWAWAY_EXPENSE_LEDGER,
                                        "amount": "1.00", "narration": narration, "post_dated": post_dated}))
    found = [v for v in parse_vouchers(await ctx.send(step, voucher_request("S0P16Throwaway", THROWAWAY_FIELDS, company)))
             if v["header"].get("NARRATION") == narration]
    after = _balances(await ctx.send(ledger_step, _ledgers_request(company)))
    cash_after = after.get(CASH, {}).get("closing_balance")
    ctx.pause(f"Delete the voucher with narration {narration!r} (open it, Alt+D). (company: {company!r})",
              Action("delete_voucher", {"company": company, "ref": ref}))
    ctx.resolve_abort(note)
    return {"found": bool(found), "is_post_dated_exported": found[0]["header"].get("ISPOSTDATED", "") if found else "",
            "cash_before": cash_before, "cash_after": cash_after, "included_in_closing": cash_after != cash_before}


def _rule(future: dict, post_dated: dict) -> str:
    as_of = ("the period end (31-03-2026), not Tally's current date" if future["included_in_closing"]
             else "Tally's current date (F2), not the period end")
    if not post_dated["found"]:
        pd = "the post-dated voucher wasn't found after the create, so the post-dated rule is still open"
    else:
        pd = (f"post-dated vouchers are {'included' if post_dated['included_in_closing'] else 'excluded'}; "
              f"IsPostDated exported {post_dated['is_post_dated_exported'] or '(empty)'!r}")
    return f"Rung 1 rule (Part 1 §6): ClosingBalance is as of {as_of}; {pd}."


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    ledgers = _balances(await ctx.send("ledgers", _ledgers_request(company)))
    if not ledgers:
        return PartResult(Outcome.BLOCKED, "The Ledger collection came back empty — is company A open?")
    groups = parse_parents(await ctx.send("groups", master_request("S0P16Groups", "Group", ["Name", "Parent"], company)))
    vouchers = parse_vouchers(await ctx.send("vouchers_fy", voucher_request("S0P16Vouchers", VOUCHER_FIELDS, company)))
    tb_rows = {row["account_name"]: row["closing_balance"] for row in parse_trial_balance(
        await ctx.send("tb_fy_end", wrap_report("Trial Balance", A_FY_FROM, A_FY_TO, company)))}
    stock_values = [row["closing_value"] for row in parse_stock_summary(
        await ctx.send("stock_summary_fy_end", wrap_report("Stock Summary", A_FY_FROM, A_FY_TO, company)))]
    stock_total = sum((v for v in stock_values if v is not None), ZERO) if stock_values else None

    kinds = _kinds(ledgers, groups)
    nominal = _nominal(ledgers, kinds)
    bad_lines, empty_for_zero = _lines_check(ledgers, kinds, ledger_movements(vouchers))
    group_cmp = _group_compare(ledgers, kinds, groups, tb_rows, stock_total)
    debtors, creditors = _party_totals(ledgers, groups)
    ctx.observe("ledger_kinds", {k: sum(1 for v in kinds.values() if v == k) for k in ("bs", "pl", "special")})
    ctx.observe("nominal", nominal)
    ctx.observe("closing_vs_lines", {"mismatches": bad_lines, "empty_closing_for_zero": empty_for_zero,
                                     "vouchers": len(vouchers)})
    ctx.observe("tb_vs_rollup", group_cmp)
    ctx.observe("party_totals", {"debtors": debtors, "creditors": creditors})
    ctx.observe("special_ledgers", {n: ledgers[n]["closing_balance"] for n, k in kinds.items() if k == "special"})

    ui = _ui_compare(ctx, ledgers)
    ctx.observe("ui_compare", ui)
    as_on = await _as_on(ctx, ledgers, kinds, vouchers)
    ctx.observe("as_on", as_on)
    cash_before = ledgers.get(CASH, {}).get("closing_balance")
    future = await _throwaway(ctx, ref=FUTURE_REF, narration=FUTURE_NARRATION, post_dated=False, step="future_voucher",
                              ledger_step="ledgers_with_future_voucher", cash_before=cash_before)
    post_dated = await _throwaway(ctx, ref=POST_DATED_REF, narration=POST_DATED_NARRATION, post_dated=True,
                                  step="post_dated_voucher", ledger_step="ledgers_with_post_dated",
                                  cash_before=cash_before)
    ctx.observe("future_voucher", future)
    ctx.observe("post_dated_voucher", post_dated)
    rule, as_on_note = _rule(future, post_dated), _as_on_note(as_on)

    failures: list[str] = []
    if bad_lines:
        failures.append(f"ClosingBalance ≠ opening + Σ lines for {len(bad_lines)} balance-sheet ledger(s) "
                        f"({', '.join(sorted(bad_lines)[:5])})")
    if -debtors != SEED_RECEIVABLE:
        failures.append(f"Σ debtors {-debtors} ≠ the Bills Receivable anchor {SEED_RECEIVABLE}")
    if creditors != SEED_PAYABLE:
        failures.append(f"Σ creditors {creditors} ≠ the Bills Payable anchor {SEED_PAYABLE}")
    ui_bad = sorted(name for name, entry in ui.items() if entry["match"] is False)
    if ui_bad:
        failures.append(f"the Tally UI shows another balance for {', '.join(ui_bad)}")
    if failures:
        return PartResult(Outcome.FAILED, "; ".join(failures), spec_impact=f"{FAILED_IMPACT} {rule}")

    differences: list[str] = []
    impacts: list[str] = []
    if nominal["nonzero"]:
        differences.append(f"{len(nominal['nonzero'])} nominal ledger(s) have a non-zero ClosingBalance")
        impacts.append("Rung 1 picks balance-sheet ledgers by group nature, never by 'ClosingBalance = 0' (Part 1 §6).")
    mismatched = sorted(group for group, entry in group_cmp.items() if not entry["match"])
    by_stock = [group for group in mismatched if group_cmp[group].get("explained_by_stock")]
    other = [group for group in mismatched if group not in by_stock]
    if by_stock:
        differences.append(f"TB row(s) {', '.join(by_stock)} = ledger rollup ± closing stock")
        impacts.append("Rung 2 adds the Stock Summary closing value to the stock-bearing group before comparing with "
                       "the TB row (Part 1 §6).")
    if other:
        differences.append(f"TB row(s) {', '.join(other)} ≠ ledger rollup")
        impacts.append("Rung 2's group rollup doesn't reproduce these TB rows; the recorded per-group figures decide the "
                       "comparison rule before S1 (Part 1 §6).")
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences), spec_impact=" ".join([*impacts, rule, as_on_note]))
    ui_note = "" if any(entry["match"] is not None for entry in ui.values()) else \
        " (UI balances not read — automated or skipped; a later manual check)"
    return PartResult(Outcome.CONFIRMED, "ClosingBalance = opening + Σ lines for every balance-sheet ledger; debtors and "
                                         "creditors match the anchors; TB rows = ledger rollup" + ui_note,
                      spec_impact=f"{rule} {as_on_note}")


PROBE = Probe(
    id=16,
    name="ledger_closing_balance",
    question="Does LEDGER.ClosingBalance equal Tally's own balances (lines, TB, UI)? Nominal = 0? As-on? As-of date and "
             "post-dated vouchers?",
    feeds=("decision 11", "R30", "Part 2 Rule 1"),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0, 1, 2),
    mutating=True,
    educational_sensitive=True,
)
```

- [x] **Step 6: Register probe 16** — in `v2/probes/registry.py` replace its line with:

```python
    ProbeInfo(16, "ledger_closing_balance", "A+B", "B", module="v2.probes.p16_ledger_closing_balance"),
```

- [x] **Step 7: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 87** (`test_reads.py` 8, `test_p16_ledger_closing_balance.py` 7).

---
### Task 7: Probe 17 (ledger-level TB) + probe 19 (counter stability)

**Files:**
- Create: `v2/probes/p17_ledger_level_tb.py`, `v2/probes/p19_counter_stability.py`
- Modify: `v2/probes/registry.py` (probes 17, 19 `module=`)
- Test: `v2/tests/probes/test_p17_ledger_level_tb.py`, `v2/tests/probes/test_p19_counter_stability.py`

**Interfaces:**
- Consumes: `wrap_report`, `COMPANY_PLACEHOLDER`, `ProbeContext.try_send/send/counters/company_names/last_response/
  confirm_request/pause/on_abort/resolve_abort`, `reads.master_request/parse_parents/tb_rows_any_depth/top_group/
  stock_bearing_groups/A_FY_FROM/A_FY_TO/ZERO`, `Action`, `THROWAWAY_DATE_TEXT`, `THROWAWAY_EXPENSE_LEDGER`
- Produces:
  - `p17_ledger_level_tb`: `PROBE` (id 17, part "A", `requires=(0, 1)`), `EXPLODE_CANDIDATES`, `CANDIDATE_TIMEOUT_S`,
    `evaluate(text, ledger_parents, group_parents, baseline) -> dict`; confirmed request `ledger_level_tb`
    (`{"probe": 17, "xml_template", "candidate", "note"}`) when a candidate works
  - `p19_counter_stability`: `PROBE` (id 19, part "A", `requires=(0, 1)`, mutating), `QUIET_CAPTURES`, `VOUCHER_REF`,
    `NARRATION`

**Probe 17 (A)** — spec §7: TB `TYPE=Data` with each *candidate* explode / ledger-wise static variable, 60 s timeout each.
- Candidates (all guesses, recorded one by one): `EXPLODEFLAG=Yes`, `SVEXPLODEFLAG=Yes`, `ISLEDGERWISE=Yes`,
  `LEDGERWISE=Yes`, `EXPLODEFLAG=Yes` + `EXPLODEALLLEVELS=Yes`.
- Steps: `tb_exploded_{explodeflag,svexplodeflag,isledgerwise,ledgerwise,explodealllevels}`; extra steps `ledger_list`,
  `group_list` (to tell ledger rows from group rows and roll them up).
- Records per candidate: error, elapsed ms, bytes, rows, ledger rows, per-group mismatches (the stock-bearing group is
  skipped — its row may carry closing stock, which no ledger holds), and after an error whether Tally still answers.
- **CONFIRMED** if a candidate returns ledger rows whose per-group sums equal the group rows (request stored as
  `ledger_level_tb`); **DIFFERENT** if ledger rows come back but don't sum; **FAILED** if no candidate returns ledger
  rows, or a candidate leaves Tally unresponsive (the probe stops there — restart Tally); **BLOCKED** without probe 0's
  TB baseline.

**Probe 19 (A)** — spec §7 steps 1–3:
- 3 quiet captures `capture_quiet_{n}_{counters_start,ledgers,tb,counters_end}`; pause `view_report` (a person opens and
  closes the Balance Sheet; the operator exports it via XML) → `after_ui_view`; one moving capture
  `capture_moving_{counters_start,ledgers,tb,counters_end}` with a `create_voucher` pause (₹1, "S0-throwaway 19")
  between the ledger list and the TB, then a `delete_voucher` pause.
- **FAILED** if quiet captures aren't stable (spec impact: the guard would abort every run) or the mid-capture entry
  isn't detected (the guard can't see concurrent entry); **DIFFERENT** if viewing the report moves the counters (the
  retry policy must tolerate it); **CONFIRMED** otherwise.

- [x] **Step 1: Write the failing tests**

`v2/tests/probes/test_p17_ledger_level_tb.py`:
```python
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
```

`v2/tests/probes/test_p19_counter_stability.py`:
```python
from v2.probes import p19_counter_stability as p19
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import COMPANY_A, FakeTally, ScriptedIO, make_harness, objects_xml, ready_store, tb_xml


def _fake(state, drift=False):
    fake = FakeTally([COMPANY_A])

    def counters(body):
        if drift:
            state["AltMstId"] += 1
        return objects_xml("COMPANY", [{"Name": COMPANY_A, "GUID": "g-1", "AltVchId": str(state["AltVchId"]),
                                        "AltMstId": str(state["AltMstId"]), "BooksFrom": "20250401",
                                        "LastVoucherDate": "20260301", "AlterID": "1"}])

    fake.route("S0CompanyCounters", counters)
    fake.route("S0P19Ledgers", lambda body: objects_xml("LEDGER", [{"Name": "Cash", "ClosingBalance": "-900.00"}]))
    fake.route("<ID>Trial Balance</ID>", lambda body: tb_xml([("Capital Account", "", "1000.00")]))
    return fake


def _io(state, voucher_moves=True, view_moves=False):
    def on_action(action):
        if action.kind == "create_voucher" and voucher_moves:
            state["AltVchId"] += 1
        elif action.kind == "delete_voucher":
            state["AltVchId"] += 3
        elif action.kind == "view_report" and view_moves:
            state["AltMstId"] += 1
    return ScriptedIO(on_action=on_action)


async def _run(tmp_path, fake, io):
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    await run_probe(p19.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return store.probe_entry(19)["parts"]["A"]


def _state():
    return {"AltVchId": 50, "AltMstId": 266}


async def test_quiet_captures_stable_and_mid_capture_entry_detected(tmp_path):
    state = _state()
    io = _io(state)
    part = await _run(tmp_path, _fake(state), io)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["quiet_stable"] is True
    assert part["observations"]["mid_capture_entry_detected"] is True
    assert [a.kind for a in io.actions] == ["view_report", "create_voucher", "delete_voucher"]
    assert len(part["fixtures"]) == 3 * 4 + 1 + 4
    assert "p19_A_capture_quiet_3_counters_end.xml" in part["fixtures"]
    assert "p19_A_after_ui_view.xml" in part["fixtures"]
    assert "p19_A_capture_moving_tb.xml" in part["fixtures"]


async def test_viewing_a_report_that_moves_counters_is_different(tmp_path):
    state = _state()
    part = await _run(tmp_path, _fake(state), _io(state, view_moves=True))
    assert part["outcome"] == "DIFFERENT"
    assert "retry policy" in part["spec_impact"]


async def test_mid_capture_entry_not_seen_fails(tmp_path):
    state = _state()
    part = await _run(tmp_path, _fake(state), _io(state, voucher_moves=False))
    assert part["outcome"] == "FAILED"
    assert "can't see" in part["spec_impact"]


async def test_counters_moving_with_no_activity_fails(tmp_path):
    state = _state()
    part = await _run(tmp_path, _fake(state, drift=True), _io(state))
    assert part["outcome"] == "FAILED"
    assert "nobody" in part["summary"]
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p17_ledger_level_tb.py v2/tests/probes/test_p19_counter_stability.py -q`
Expected: FAIL — `ImportError: cannot import name 'p17_ledger_level_tb'`.

- [x] **Step 3: Write `v2/probes/p17_ledger_level_tb.py`**

```python
"""Probe 17 — can the Trial Balance be exported at ledger level via TYPE=Data? (S0 spec §7 "Probe 17")

Feeds decision 11 and R3 (Part 1 §6 rung 2). Each candidate static variable is sent once with a 60 s timeout; after a
failed one Tally must still answer a cheap read, or the probe stops (Tally may be stuck computing).
"""
from __future__ import annotations

from decimal import Decimal

from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER, wrap_report
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.reads import (A_FY_FROM, A_FY_TO, ZERO, master_request, parse_parents, stock_bearing_groups,
                             tb_rows_any_depth, top_group)

# Candidate static variables that might switch the TB to ledger level. None is verified; the probe records which work.
EXPLODE_CANDIDATES: dict[str, dict[str, str]] = {
    "explodeflag": {"EXPLODEFLAG": "Yes"},                                  # Tally's Alt+F1 'Detailed' switch
    "svexplodeflag": {"SVEXPLODEFLAG": "Yes"},                              # the same, SV-prefixed like other export vars
    "isledgerwise": {"ISLEDGERWISE": "Yes"},                                # the TB's F5 'Ledger-wise' button (guessed)
    "ledgerwise": {"LEDGERWISE": "Yes"},                                    # a shorter spelling of that guess
    "explodealllevels": {"EXPLODEFLAG": "Yes", "EXPLODEALLLEVELS": "Yes"},  # detailed + every level (guessed)
}
CANDIDATE_TIMEOUT_S = 60.0


def evaluate(text: str, ledger_parents: dict[str, str], group_parents: dict[str, str],
             baseline: dict[str, str]) -> dict:
    """Ledger rows in an exploded TB, and whether their per-primary-group sums equal the group rows."""
    rows = tb_rows_any_depth(text)
    tops = set(baseline)
    stock_groups = stock_bearing_groups(group_parents)
    group_rows: dict[str, Decimal | None] = {}
    ledger_rows: list[dict] = []
    for row in rows:
        # The first row named after a primary group is that group's total (company A has a group AND a ledger called
        # "Capital Account"); later rows carrying a ledger's name are ledger rows.
        if row["name"] in tops and row["name"] not in group_rows:
            group_rows[row["name"]] = row["closing"]
        elif row["name"] in ledger_parents:
            ledger_rows.append(row)
    sums: dict[str, Decimal] = {}
    for row in ledger_rows:
        parent = ledger_parents[row["name"]]
        top = "Primary" if parent in ("", "Primary") else top_group(parent, group_parents)
        sums[top] = sums.get(top, ZERO) + (row["closing"] or ZERO)
    mismatches: dict[str, dict] = {}
    for group in sorted(tops - stock_groups):
        reference = group_rows.get(group)
        if reference is None:
            text_value = baseline.get(group, "")
            reference = Decimal(text_value) if text_value not in ("", "None") else ZERO
        if sums.get(group, ZERO) != reference:
            mismatches[group] = {"group_row": reference, "ledger_sum": sums.get(group, ZERO)}
    return {"rows": len(rows), "ledger_rows": len(ledger_rows), "sums_match": bool(ledger_rows) and not mismatches,
            "mismatches": mismatches, "stock_bearing_skipped": sorted(tops & stock_groups)}


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    baseline = ctx.store.environment.get("company_a_tb_baseline") or {}
    if not baseline:
        return PartResult(Outcome.BLOCKED, "No TB baseline from probe 0 — run probe 0 first.")
    ledger_parents = parse_parents(await ctx.send(
        "ledger_list", master_request("S0P17Ledgers", "Ledger", ["Name", "Parent"], company)), "LEDGER")
    group_parents = parse_parents(await ctx.send(
        "group_list", master_request("S0P17Groups", "Group", ["Name", "Parent"], company)))
    results: dict[str, dict] = {}
    working: str | None = None
    for key, variables in EXPLODE_CANDIDATES.items():
        xml = wrap_report("Trial Balance", A_FY_FROM, A_FY_TO, company, extra_vars=variables)
        text, error = await ctx.try_send(f"tb_exploded_{key}", xml, timeout=CANDIDATE_TIMEOUT_S)
        entry: dict = {"variables": variables, "error": error}
        if error is None:
            entry.update(elapsed_ms=ctx.last_response.elapsed_ms, bytes=ctx.last_response.response_bytes,
                         **evaluate(text, ledger_parents, group_parents, baseline))
            if working is None and entry["sums_match"]:
                working = key
        else:
            try:
                names = await ctx.company_names()
            except ProbeBlocked as exc:
                entry["tally_after"] = f"no answer: {exc}"
                results[key] = entry
                ctx.observe("candidates", results)
                return PartResult(Outcome.FAILED, f"Candidate {key!r} ({error['kind']}) left Tally unresponsive — "
                                                  "restart Tally before anything else",
                                  spec_impact="An exploded TB can hang Tally: rung 2 stays at group level and "
                                              "month-bisect localises (decision 11, R3); the agent never sends it.")
            entry["tally_after"] = f"answered: {names}"
        results[key] = entry
    ctx.observe("candidates", results)
    ctx.observe("working_variable", working)
    if working is not None:
        chosen = results[working]
        ctx.confirm_request("ledger_level_tb", wrap_report("Trial Balance", A_FY_FROM, A_FY_TO, COMPANY_PLACEHOLDER,
                                                           extra_vars=EXPLODE_CANDIDATES[working]),
                            candidate=working, note="S2 substitutes SVFROMDATE / SVTODATE")
        return PartResult(Outcome.CONFIRMED,
                          f"{working!r} returns {chosen['ledger_rows']} ledger rows whose per-group sums equal the TB "
                          f"group rows ({chosen['elapsed_ms']} ms, {chosen['bytes']} bytes under Wine)",
                          spec_impact=f"Rung 2 can compare at ledger level with {EXPLODE_CANDIDATES[working]} and "
                                      "month-bisect gets cheaper (decision 11); timing is re-measured on tier C.")
    with_rows = [key for key, entry in results.items() if entry.get("ledger_rows", 0) > 0]
    if with_rows:
        return PartResult(Outcome.DIFFERENT, f"Ledger rows come back ({', '.join(with_rows)}) but their per-group sums "
                                             "don't equal the TB group rows",
                          spec_impact="The exploded TB's ledger rows don't sum to its groups: rung 2 stays group-level "
                                      "until the recorded mismatch is explained (decision 11, R3).")
    return PartResult(Outcome.FAILED, "No candidate variable returns ledger-level TB rows",
                      spec_impact="No ledger-level TB via TYPE=Data: rung 2 stays group-level and month-bisect does "
                                  "the localising (decision 11, R3).")


PROBE = Probe(
    id=17,
    name="ledger_level_tb",
    question="Can the Trial Balance be exported at ledger level via TYPE=Data, safely, and do its rows sum to the groups?",
    feeds=("decision 11", "R3"),
    parts={"A": run_a},
    requires=(0, 1),
)
```

- [x] **Step 4: Write `v2/probes/p19_counter_stability.py`**

```python
"""Probe 19 — do AltVchId / AltMstId hold still across a multi-call capture? (S0 spec §7 "Probe 19")

Feeds the quiescence guard (Part 1 §6): read the counters right before and right after a parity capture and discard
the run if they moved. That needs quiet captures to be stable, a report view not to move them, and a voucher entered
mid-capture to move them.
"""
from __future__ import annotations

from typing import Callable

from v2.agent.tally.envelopes import wrap_report
from v2.probes.actions import Action
from v2.probes.companies import THROWAWAY_DATE_TEXT, THROWAWAY_EXPENSE_LEDGER
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import A_FY_FROM, A_FY_TO, master_request

QUIET_CAPTURES = 3
WATCHED = ("AltVchId", "AltMstId")
VOUCHER_REF = "p19-mid-capture"
NARRATION = "S0-throwaway 19"


def _watched(counters: dict[str, str]) -> dict[str, str]:
    return {field: counters.get(field, "") for field in WATCHED}


async def _capture(ctx: ProbeContext, prefix: str, between: Callable[[], None] | None = None) -> dict:
    """counters → ledger list → (between) → TB → counters, as a parity capture does."""
    start = _watched(await ctx.counters(f"{prefix}_counters_start"))
    await ctx.send(f"{prefix}_ledgers",
                   master_request("S0P19Ledgers", "Ledger", ["Name", "ClosingBalance"], ctx.company_name))
    if between is not None:
        between()
    await ctx.send(f"{prefix}_tb", wrap_report("Trial Balance", A_FY_FROM, A_FY_TO, ctx.company_name))
    end = _watched(await ctx.counters(f"{prefix}_counters_end"))
    return {"start": start, "end": end, "stable": start == end}


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    quiet = [await _capture(ctx, f"capture_quiet_{n}") for n in range(1, QUIET_CAPTURES + 1)]
    readings = [capture["start"] for capture in quiet] + [capture["end"] for capture in quiet]
    quiet_stable = all(reading == readings[0] for reading in readings)
    ctx.observe("quiet_captures", quiet)
    ctx.observe("quiet_stable", quiet_stable)

    ctx.pause("In Tally, open the Balance Sheet (Gateway of Tally → Balance Sheet), look at it, then close it. "
              "Change nothing.",
              Action("view_report", {"company": company, "report": "Balance Sheet", "from_date": A_FY_FROM,
                                     "to_date": A_FY_TO}))
    after_view = _watched(await ctx.counters("after_ui_view"))
    view_moved = after_view != quiet[-1]["end"]
    ctx.observe("after_ui_view", after_view)
    ctx.observe("view_moved_counters", view_moved)

    note = f"Delete the voucher with narration {NARRATION!r} if it still exists"

    def enter_voucher() -> None:
        ctx.on_abort(note)
        ctx.pause(f"Now, in the middle of a capture: create a Payment voucher dated {THROWAWAY_DATE_TEXT}: Cash → "
                  f"{THROWAWAY_EXPENSE_LEDGER}, ₹1, narration {NARRATION!r}. Save it. (company: {company!r})",
                  Action("create_voucher", {"company": company, "ref": VOUCHER_REF, "ledger": THROWAWAY_EXPENSE_LEDGER,
                                            "amount": "1.00", "narration": NARRATION}))

    moving = await _capture(ctx, "capture_moving", between=enter_voucher)
    ctx.pause(f"Delete the voucher with narration {NARRATION!r} (open it, Alt+D). (company: {company!r})",
              Action("delete_voucher", {"company": company, "ref": VOUCHER_REF}))
    ctx.resolve_abort(note)
    detected = not moving["stable"]
    ctx.observe("moving_capture", moving)
    ctx.observe("mid_capture_entry_detected", detected)

    if not quiet_stable:
        return PartResult(Outcome.FAILED, "Counters moved between reads with nobody entering anything",
                          spec_impact="The quiescence guard would abort every parity run: Part 1 §6 needs another "
                                      "quiescence signal before S2 (record which counter drifts).")
    if not detected:
        return PartResult(Outcome.FAILED, "A voucher entered mid-capture didn't move AltVchId / AltMstId",
                          spec_impact="The quiescence guard can't see a concurrent entry: parity needs another guard "
                                      "(e.g. re-read the lines after the snapshot) before S1 (Part 1 §6).")
    if view_moved:
        return PartResult(Outcome.DIFFERENT, "Opening a report moved the counters",
                          spec_impact="A report view moves the counters, so the guard aborts while someone browses: the "
                                      "retry policy (Part 1 §6 'Schedule and trigger') must tolerate repeated "
                                      "aborted_moving runs.")
    return PartResult(Outcome.CONFIRMED, "Quiet captures are stable, a report view doesn't move the counters, and a "
                                         "mid-capture voucher is detected")


PROBE = Probe(
    id=19,
    name="counter_stability",
    question="Do AltVchId / AltMstId hold still across a quiet multi-call capture, and move when a voucher is entered?",
    feeds=("quiescence guard",),
    parts={"A": run_a},
    requires=(0, 1),
    mutating=True,
)
```

- [x] **Step 5: Register probes 17 and 19** — in `v2/probes/registry.py`:

```python
    ProbeInfo(17, "ledger_level_tb", "A", "B", module="v2.probes.p17_ledger_level_tb"),
```
```python
    ProbeInfo(19, "counter_stability", "A", "B", module="v2.probes.p19_counter_stability"),
```

- [x] **Step 6: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 95** (`test_p17_ledger_level_tb.py` 4, `test_p19_counter_stability.py` 4).

---
### Task 8: Probe 18 (historical reports, A part)

**Files:**
- Create: `v2/probes/p18_historical_reports.py`
- Modify: `v2/probes/registry.py` (probe 18 `module=`)
- Test: `v2/tests/probes/test_p18_historical_reports.py`

**Interfaces:**
- Consumes: `wrap_report`, `parse_trial_balance`, `parse_bills`, `parse_ledger_list`, `read_objects`,
  `reads.voucher_request/master_request/parse_vouchers/parse_parents/primary_lines/ledger_movements/is_countable/
  tally_date/dmy/qty_number/amount/ancestors/top_group/stock_bearing_groups/stock_rows_any_depth/ZERO/A_FY_FROM`
- Produces: `PROBE` (id 18, parts {"A"}, `planned_parts=("A", "B")`, `requires=(0, 1)`, educational-sensitive),
  `TB_AS_ON = "31-10-2025"`, `BILLS_AS_ON = "30-09-2025"`, `tb_verdict(...)`, `pending_bills(...)`, `stock_verdict(...)`

**Probe 18 (A)** — spec §7:
- Steps: `tb_asof_2025-10-31` (TB, SVFROMDATE 01-04-2025, SVTODATE 31-10-2025), `vouchers_to_2025-10-31` (voucher
  collection to 31-10-2025 with lines, bills, inventory), `bills_receivable_asof_2025-09-30`,
  `bills_payable_asof_2025-09-30` (both dates 30-09-2025), `stock_summary_asof_2025-09-30` (SVTODATE 30-09-2025 and the
  *candidate* `EXPLODEFLAG=Yes`, because the seed's Stock Summary top level lists stock groups, not items). Extra steps:
  `ledger_list` (Name, Parent, OpeningBalance), `group_list`, `stock_item_openings` (StockItem Name, Parent, BaseUnits,
  OpeningBalance).
- TB sub-verdict: each primary group's TB row vs Σ (ledger opening + postings ≤ 31-10-2025) over its ledgers. The
  stock-bearing group is compared and recorded separately and doesn't decide the verdict (probe 16 settles stock).
- Bills sub-verdict: per bill (party|ref) pending on 30-09-2025 from the bill allocations of vouchers ≤ that date vs the
  report (seed: no receivable bills yet on 30-09-2025 — recorded as a weak check; payable P001 ₹6,43,100).
- Stock sub-verdict: quantities exact vs opening + inventory lines ≤ 30-09-2025 (ISDEEMEDPOSITIVE Yes = inward), per item
  row, or per stock-group row when the report only gives groups; values recorded only.
- Part outcome = the worse of the two sub-verdicts (spec §5.1): **FAILED** (TB) → spec impact "parity is suspended during
  the backfill (R30)"; **FAILED** (bills/stock) → "those tiles lose their month-end comparison"; both sub-verdicts in
  `observations["sub_verdicts"]`; **CONFIRMED** when both hold.

- [x] **Step 1: Write the failing tests** — `v2/tests/probes/test_p18_historical_reports.py`

```python
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
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p18_historical_reports.py -q`
Expected: FAIL — `ImportError: cannot import name 'p18_historical_reports'`.

- [x] **Step 3: Write `v2/probes/p18_historical_reports.py`**

```python
"""Probe 18 — do TB, Bills and Stock Summary as-on a past date return correct history? (S0 spec §7 "Probe 18", A part)

Feeds decision 11, R30 and Parts 2 + 3. Two sub-verdicts (spec §5.1): TB, and bills/stock; the part outcome is the
worse of the two. The B part (TB as-on 31-03-2023 vs the dataset) comes in plan part 3.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from v2.agent.tally.envelopes import wrap_report
from v2.agent.tally.reports import parse_bills, parse_ledger_list, parse_trial_balance
from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import (A_FY_FROM, ZERO, amount, ancestors, dmy, is_countable, ledger_movements, master_request,
                             parse_parents, parse_vouchers, primary_lines, qty_number, stock_bearing_groups,
                             stock_rows_any_depth, tally_date, top_group, voucher_request)

TB_AS_ON = "31-10-2025"
BILLS_AS_ON = "30-09-2025"
VOUCHER_FIELDS = ["Date", "VoucherTypeName", "MasterId", "IsCancelled", "IsOptional", "IsPostDated",
                  "AllLedgerEntries", "LedgerEntries", "AllInventoryEntries"]
STOCK_FIELDS = ["Name", "Parent", "BaseUnits", "OpeningBalance"]
STOCK_EXPLODE_CANDIDATE = {"EXPLODEFLAG": "Yes"}      # probe 17's first candidate: items under their stock groups
TB_IMPACT = ("A TB as-on a past date isn't history: there is no valid parity anchor while the backfill is incomplete, "
             "so parity is suspended during the backfill (R30, decision 11).")
BILLS_STOCK_IMPACT = ("Bills Receivable / Payable or Stock Summary as-on a past date aren't history: those tiles lose "
                      "their month-end comparison (Part 1 probe 18, Part 3).")


def tb_verdict(tb_rows: dict[str, Decimal | None], ledgers: dict[str, dict], groups: dict[str, str],
               vouchers: list[dict], as_on: date) -> dict:
    moves = ledger_movements(vouchers, up_to=as_on)
    computed: dict[str, Decimal] = {}
    for name, row in ledgers.items():
        parent = row["parent_group"]
        if parent in ("", "Primary"):
            continue
        top = top_group(parent, groups)
        computed[top] = computed.get(top, ZERO) + (row["opening_balance"] or ZERO) + moves.get(name, ZERO)
    stock_groups = stock_bearing_groups(groups)
    compared: dict[str, dict] = {}
    stock_side: dict[str, dict] = {}
    for group in sorted(set(tb_rows) | {g for g, v in computed.items() if v != ZERO}):
        tb_value, mine = tb_rows.get(group), computed.get(group, ZERO)
        entry = {"tb": tb_value, "computed": mine, "match": (tb_value if tb_value is not None else ZERO) == mine}
        (stock_side if group in stock_groups else compared)[group] = entry
    mismatched = sorted(group for group, entry in compared.items() if not entry["match"])
    return {"verdict": "FAILED" if mismatched or not compared else "CONFIRMED", "groups": compared,
            "stock_bearing": stock_side, "mismatched": mismatched}


def pending_bills(vouchers: list[dict], ledgers: dict[str, dict], groups: dict[str, str], as_on: date,
                  side: str) -> dict[str, Decimal]:
    """'party|bill' → pending on `as_on`, from the bill allocations on party lines (receivable: debtors, payable: creditors)."""
    wanted = "Sundry Debtors" if side == "receivable" else "Sundry Creditors"
    totals: dict[str, Decimal] = {}
    for voucher in vouchers:
        when = tally_date(voucher["header"].get("DATE", ""))
        if not is_countable(voucher) or when is None or when > as_on:
            continue
        for item in primary_lines(voucher):
            party = item["fields"].get("LEDGERNAME", "")
            row = ledgers.get(party)
            if row is None or wanted not in ancestors(row["parent_group"], groups):
                continue
            for bill in item["bills"]:
                value = amount(bill.get("AMOUNT"))
                if value is not None:
                    key = f"{party}|{bill.get('NAME', '')}"
                    totals[key] = totals.get(key, ZERO) + value
    sign = Decimal("-1") if side == "receivable" else Decimal("1")
    return {key: sign * value for key, value in totals.items() if value != ZERO}


def _bills_side(report_text: str, expected: dict[str, Decimal]) -> dict:
    reported = {f"{b['party_name']}|{b['bill_number']}": b["amount"] for b in parse_bills(report_text)}
    return {"reported": reported, "expected": expected, "match": reported == expected,
            "weak": not reported and not expected}


def stock_verdict(rows: list[dict], items: list[dict[str, str]], vouchers: list[dict], as_on: date) -> dict:
    expected = {item["Name"]: qty_number(item["OpeningBalance"]) or ZERO for item in items}
    parent = {item["Name"]: item["Parent"] for item in items}
    for voucher in vouchers:
        when = tally_date(voucher["header"].get("DATE", ""))
        if not is_countable(voucher) or when is None or when > as_on:
            continue
        for inv in voucher["inventory"]:
            name = inv["fields"].get("STOCKITEMNAME", "")
            qty = qty_number(inv["fields"].get("ACTUALQTY", ""))
            if name and qty is not None:
                inward = inv["fields"].get("ISDEEMEDPOSITIVE", "") == "Yes"
                expected[name] = expected.get(name, ZERO) + (abs(qty) if inward else -abs(qty))
    by_group: dict[str, Decimal] = {}
    for name, qty in expected.items():
        by_group[parent.get(name, "")] = by_group.get(parent.get(name, ""), ZERO) + qty
    compared: dict[str, dict] = {}
    for row in rows:
        if row["qty"] is None:
            continue
        if row["name"] in expected:
            want = expected[row["name"]]
        elif row["name"] in by_group:
            want = by_group[row["name"]]
        else:
            continue
        compared[row["name"]] = {"reported": row["qty"], "expected": want, "value": row["value"],
                                 "match": row["qty"] == want}
    mismatches = sorted(name for name, entry in compared.items() if not entry["match"])
    return {"verdict": "CONFIRMED" if compared and not mismatches else "FAILED", "compared": compared,
            "mismatches": mismatches, "item_rows": sum(1 for row in rows if row["name"] in expected),
            "direction_rule": "ISDEEMEDPOSITIVE=Yes is inward"}


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    tb_date, bills_date = dmy(TB_AS_ON), dmy(BILLS_AS_ON)
    tb_rows = {row["account_name"]: row["closing_balance"] for row in parse_trial_balance(
        await ctx.send("tb_asof_2025-10-31", wrap_report("Trial Balance", A_FY_FROM, TB_AS_ON, company)))}
    vouchers = parse_vouchers(await ctx.send("vouchers_to_2025-10-31",
                                             voucher_request("S0P18Vouchers", VOUCHER_FIELDS, company, to_date=TB_AS_ON)))
    ledgers = {row["name"]: row for row in parse_ledger_list(await ctx.send(
        "ledger_list", master_request("S0P18Ledgers", "Ledger", ["Name", "Parent", "OpeningBalance"], company)))}
    groups = parse_parents(await ctx.send("group_list", master_request("S0P18Groups", "Group", ["Name", "Parent"], company)))
    tb = tb_verdict(tb_rows, ledgers, groups, vouchers, tb_date)

    receivable = await ctx.send("bills_receivable_asof_2025-09-30",
                                wrap_report("Bills Receivable", BILLS_AS_ON, BILLS_AS_ON, company))
    payable = await ctx.send("bills_payable_asof_2025-09-30", wrap_report("Bills Payable", BILLS_AS_ON, BILLS_AS_ON, company))
    bills = {"receivable": _bills_side(receivable, pending_bills(vouchers, ledgers, groups, bills_date, "receivable")),
             "payable": _bills_side(payable, pending_bills(vouchers, ledgers, groups, bills_date, "payable"))}
    stock_text = await ctx.send("stock_summary_asof_2025-09-30",
                                wrap_report("Stock Summary", A_FY_FROM, BILLS_AS_ON, company,
                                            extra_vars=STOCK_EXPLODE_CANDIDATE))
    items = read_objects(await ctx.send("stock_item_openings",
                                        master_request("S0P18Stock", "StockItem", STOCK_FIELDS, company)),
                         "STOCKITEM", STOCK_FIELDS)
    stock = stock_verdict(stock_rows_any_depth(stock_text), items, vouchers, bills_date)
    bills_ok = bills["receivable"]["match"] and bills["payable"]["match"]
    sub = {"tb": tb["verdict"], "bills_stock": "CONFIRMED" if bills_ok and stock["verdict"] == "CONFIRMED" else "FAILED"}
    ctx.observe("tb", tb)
    ctx.observe("bills", bills)
    ctx.observe("stock", stock)
    ctx.observe("sub_verdicts", sub)

    problems, impacts = [], []
    if sub["tb"] == "FAILED":
        problems.append(f"TB as-on {TB_AS_ON} ≠ opening + lines for {', '.join(tb['mismatched']) or 'every group'}")
        impacts.append(TB_IMPACT)
    if sub["bills_stock"] == "FAILED":
        wrong = [side for side in ("receivable", "payable") if not bills[side]["match"]]
        what = [f"bills {side}" for side in wrong] + ([f"stock ({', '.join(stock['mismatches']) or 'nothing comparable'})"]
                                                      if stock["verdict"] == "FAILED" else [])
        problems.append(f"as-on {BILLS_AS_ON}: {'; '.join(what)}")
        impacts.append(BILLS_STOCK_IMPACT)
    if problems:
        return PartResult(Outcome.FAILED, "; ".join(problems), spec_impact=" ".join(impacts))
    return PartResult(Outcome.CONFIRMED, f"TB as-on {TB_AS_ON}, Bills and Stock Summary as-on {BILLS_AS_ON} equal what the "
                                         "vouchers give (stock values recorded, not compared)")


PROBE = Probe(
    id=18,
    name="historical_reports",
    question="Do TB, Bills Receivable/Payable and Stock Summary as-on a past date return correct history?",
    feeds=("decision 11", "R30", "Parts 2 + 3"),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0, 1),
    educational_sensitive=True,
)
```

- [x] **Step 4: Register probe 18** — in `v2/probes/registry.py`:

```python
    ProbeInfo(18, "historical_reports", "A+B", "B", module="v2.probes.p18_historical_reports"),
```

- [x] **Step 5: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 99** (`test_p18_historical_reports.py` 4).

---
### Task 9: Read-only probes 3 (voucher IDs and flags, A part), 4 (`$AlterID > N`), 6 (nested lines, line GUID)

**Files:**
- Create: `v2/probes/p03_voucher_ids_flags.py`, `v2/probes/p04_alterid_filter.py`,
  `v2/probes/p06_nested_lines_ledger_guid.py`
- Modify: `v2/probes/registry.py` (probes 3, 4, 6 `module=`)
- Test: `v2/tests/probes/test_p03_voucher_ids_flags.py`, `v2/tests/probes/test_p04_alterid_filter.py`,
  `v2/tests/probes/test_p06_nested_lines_ledger_guid.py`

**Interfaces:**
- Consumes: `read_objects`, `get_text`, `sanitize_xml`, `ProbeContext.send/try_send/counters`,
  `reads.voucher_request/master_request/parse_vouchers/postings/POSTING_RULES/VOUCHER_CHILDOF/A_FY_FROM/A_FY_TO`
- Produces:
  - `p03_voucher_ids_flags`: `PROBE` (id 3, parts {"A"}, `planned_parts=("A", "B")`, `requires=(0,)`), `FIELDS`,
    `FLAG_CANDIDATES`, `EXPECTED_VOUCHERS = 50`
  - `p04_alterid_filter`: `PROBE` (id 4, part "A", `requires=(0, 1)`), `OBJECTS`
  - `p06_nested_lines_ledger_guid`: `PROBE` (id 6, part "A", `requires=(0,)`), `LINE_GUID_METHOD_CANDIDATES`,
    `LINE_GUID_TAG_CANDIDATES`, `LINE_GUID_TDL_FIELD`, `EXPECTED_PARTY_PAYMENTS = 4`, `EXPECTED_EXPENSE_PAYMENTS = 12`

**Probe 3 (A)** — step `vouchers_ids_flags`: every voucher with the *candidate* fields GUID, MasterID, AlterID, Date,
VoucherTypeName, VoucherNumber, Reference, PartyLedgerName, Narration, IsCancelled, IsOptional, IsPostDated.
**FAILED** if a flag field doesn't export on every voucher (spec impact: R16 filtering redesigned before S1) or GUID /
MasterID are empty or duplicated, or AlterID empty (R6); **DIFFERENT** if the count ≠ 50 or Reference ≠ the invoice number
on Sales / Purchase (taken from the seed narration "Invoice #S001"); **CONFIRMED** otherwise. (The B part — cancelled and
optional flags — is plan part 3; IsPostDated on a post-dated voucher is recorded by probe 16.)

**Probe 4 (A)** — for Voucher, Ledger, Group, StockItem: `{type}_full` (GUID, AlterID) → max M; `{type}_gt_m_minus_5`,
`{type}_gt_m`, `{type}_gt_0` with the filter `$AlterID > N`; expected sets come from the full fetch (compared by GUID:
exactly the objects with AlterID > N — AlterIDs are shared across object types, so "> M-5" can hold fewer than five of one
type); extra step `cheap_read_after` (counters). **FAILED** if any filtered set is wrong, a request errors, or Tally
doesn't answer the cheap read (rolling re-pull fallback, R6); **CONFIRMED** otherwise.

**Probe 6 (A)** — steps `vouchers_nested` (AllLedgerEntries, LedgerEntries, AllInventoryEntries fetched whole — the form
`live_tally_debug.md` shows returning nested lists), `line_guid_fetch`, `line_guid_tdl`; extra step `ledger_guids`.
- Structure vs seed: Sales/Purchase carry New Ref bills and inventory lines; Receipts Agst Ref; party Payments Agst Ref
  (4); expense Payments no bills (12). Sub-field presence counted for lines (LEDGERNAME, AMOUNT, ISDEEMEDPOSITIVE), bills
  (NAME, BILLTYPE, AMOUNT, BILLCREDITPERIOD), inventory (STOCKITEMNAME, ACTUALQTY, BILLEDQTY, RATE, AMOUNT), batches
  (GODOWNNAME, BATCHNAME, AMOUNT).
- Σ amount per voucher = 0.00 under each posting rule (`default`, `all_only`, `ledger_plus_alloc`, `all_plus_alloc`);
  the first rule that balances every voucher is recorded; debit is negative (ISDEEMEDPOSITIVE Yes ⇔ amount < 0).
- Ledger GUID on a line: (a) *candidate* line methods `AllLedgerEntries.LedgerGUID`, `AllLedgerEntries.GUID`,
  `AllLedgerEntries.LedgerMasterId` on Payment vouchers, looking for *candidate* tags LEDGERGUID, GUID, LEDGERMASTERID,
  MASTERID inside ALLLEDGERENTRIES.LIST; (b) inline TDL: a voucher collection walking `AllLedgerEntries` with
  `<COMPUTE>S0LedgerGuid : $GUID:Ledger:$LedgerName</COMPUTE>`, checked against the ledger GUIDs.
- **FAILED** if a nested list is missing (no ledger lines, no bill allocations, Sales without inventory → S1 schema change)
  or no posting rule balances every voucher / a debit isn't negative (rung 0 and the sign rule); **DIFFERENT** if bill
  types don't match the seed structure, or no route gives a ledger GUID (server name resolution stays); **CONFIRMED**
  otherwise, noting whether the GUID needs inline TDL.

- [x] **Step 1: Write the failing tests**

`v2/tests/probes/test_p03_voucher_ids_flags.py`:
```python
from v2.probes import p03_voucher_ids_flags as p03
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, make_harness, objects_xml, ready_store


def _rows():
    rows = []
    for i in range(1, 51):
        kind = "Sales" if i <= 16 else "Purchase" if i <= 24 else "Payment" if i <= 40 else "Receipt"
        ref = f"S{i:03d}" if kind == "Sales" else f"P{i - 16:03d}" if kind == "Purchase" else ""
        rows.append({"GUID": f"g-1-{i:08x}", "MasterID": str(i), "AlterID": str(100 + i), "Date": "20251001",
                     "VoucherTypeName": kind, "VoucherNumber": str(i), "Reference": ref, "PartyLedgerName": "Apex",
                     "Narration": f"Invoice #{ref} - goods" if ref else f"{kind} {i}",
                     "IsCancelled": "No", "IsOptional": "No", "IsPostDated": "No"})
    return rows


async def _run(tmp_path, rows):
    fake, _ = a_tally()
    fake.route("S0P03Vouchers", lambda body: objects_xml("VOUCHER", rows))
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    await run_probe(p03.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(3)


async def test_ids_unique_flags_present_references_right(tmp_path):
    entry = await _run(tmp_path, _rows())
    part = entry["parts"]["A"]
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert entry["remaining"] == ["B"]
    assert part["observations"]["count"] == 50
    assert part["fixtures"] == ["p03_A_vouchers_ids_flags.xml"]


async def test_a_flag_that_does_not_export_fails(tmp_path):
    rows = _rows()
    for row in rows:
        row["IsOptional"] = ""
    part = (await _run(tmp_path, rows))["parts"]["A"]
    assert part["outcome"] == "FAILED"
    assert "IsOptional" in part["summary"] and "R16" in part["spec_impact"]


async def test_reference_not_the_invoice_number_is_different(tmp_path):
    rows = _rows()
    rows[0]["Reference"] = "1"
    part = (await _run(tmp_path, rows))["parts"]["A"]
    assert part["outcome"] == "DIFFERENT"
    assert part["observations"]["wrong_references"][0]["expected"] == "S001"


async def test_duplicate_guid_fails(tmp_path):
    rows = _rows()
    rows[1]["GUID"] = rows[0]["GUID"]
    part = (await _run(tmp_path, rows))["parts"]["A"]
    assert part["outcome"] == "FAILED"
    assert "GUID" in part["summary"] and "R6" in part["spec_impact"]
```

`v2/tests/probes/test_p04_alterid_filter.py`:
```python
import re

import httpx

from v2.probes import p04_alterid_filter as p04
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import COMPANY_A, ScriptedIO, a_tally, make_harness, objects_xml, ready_store

DATA = {
    "S0P04Voucher": ("VOUCHER", [{"GUID": f"v-{i}", "AlterID": str(i), "MasterId": str(i)} for i in range(1, 11)]),
    "S0P04Ledger": ("LEDGER", [{"Name": f"L{i}", "GUID": f"l-{i}", "AlterID": str(200 + 3 * i)} for i in range(1, 8)]),
    "S0P04Group": ("GROUP", [{"Name": f"G{i}", "GUID": f"gr-{i}", "AlterID": str(300 + i)} for i in range(1, 4)]),
    "S0P04StockItem": ("STOCKITEM", [{"Name": f"I{i}", "GUID": f"s-{i}", "AlterID": str(400 + i)} for i in range(1, 16)]),
}


def _handler(marker, honour_filter=True):
    tag, rows = DATA[marker]

    def handler(body):
        match = re.search(r"\$AlterID &gt; (-?\d+)", body)
        chosen = [r for r in rows if not (match and honour_filter) or int(r["AlterID"]) > int(match.group(1))]
        return objects_xml(tag, chosen)
    return handler


async def _run(tmp_path, honour_filter=True, hang_after=False):
    fake, state = a_tally()
    for marker in DATA:
        fake.route(marker, _handler(marker, honour_filter))
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    if hang_after:
        calls = {"n": 0}
        others = [(m, h) for m, h in fake.routes if m != "S0CompanyCounters"]

        def counters(body):
            calls["n"] += 1
            if calls["n"] > 1:              # the runner's GUID read passes, the cheap read after the filters hangs
                return httpx.ReadTimeout
            return objects_xml("COMPANY", [{"Name": COMPANY_A, "GUID": "g-1", "AltVchId": "50", "AltMstId": "266"}])

        fake.routes = [("S0CompanyCounters", counters), *others]
    await run_probe(p04.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(4)["parts"]["A"]


async def test_filters_return_exactly_the_expected_objects(tmp_path):
    part = await _run(tmp_path)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    ledger = part["observations"]["checks"]["ledger"]
    assert ledger["max_alterid"] == 221
    assert ledger["filters"]["gt_m_minus_5"]["expected"] == 2          # AlterIDs 218 and 221 only
    assert len(part["fixtures"]) == 4 * 4 + 1
    assert "p04_A_stockitem_gt_m_minus_5.xml" in part["fixtures"]


async def test_filter_ignored_fails(tmp_path):
    part = await _run(tmp_path, honour_filter=False)
    assert part["outcome"] == "FAILED"
    assert "rolling re-pull" in part["spec_impact"]


async def test_tally_not_answering_after_the_filters_fails(tmp_path):
    part = await _run(tmp_path, hang_after=True)
    assert part["outcome"] == "FAILED"
    assert "stopped answering" in part["summary"]
```

`v2/tests/probes/test_p06_nested_lines_ledger_guid.py`:
```python
from v2.probes import p06_nested_lines_ledger_guid as p06
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, line, make_harness, objects_xml, ready_store, vch, vouchers_xml

GUIDS = {"Apex": "g-apex", "Samsung": "g-sam", "CGST Output": "g-cgo", "SGST Output": "g-sgo", "CGST Input": "g-cgi",
         "SGST Input": "g-sgi", "Cash": "g-cash", "HDFC": "g-hdfc", "Rent": "g-rent",
         "Sales - Electronics": "g-sales", "Purchase - Electronics": "g-purch"}


def _inventory(amount, inward):
    return [{"STOCKITEMNAME": "HP Laptop 15s", "ISDEEMEDPOSITIVE": "Yes" if inward else "No", "ACTUALQTY": "1 Nos",
             "BILLEDQTY": "1 Nos", "RATE": "100.00/Nos", "AMOUNT": amount,
             "accounting": [line("Purchase - Electronics" if inward else "Sales - Electronics", amount)],
             "batches": [{"GODOWNNAME": "Main Location", "BATCHNAME": "Primary Batch", "AMOUNT": amount}]}]


def _vouchers(receipt_bill_type="Agst Ref", bills=True, sales_party="-118.00"):
    def bill(name, kind, amount):
        return [{"NAME": name, "BILLTYPE": kind, "AMOUNT": amount, "BILLCREDITPERIOD": ""}] if bills else []
    return vouchers_xml([
        vch({"DATE": "20251001", "VOUCHERTYPENAME": "Sales", "MASTERID": "1"},
            lines=[line("Apex", sales_party, bills=bill("S001", "New Ref", "-118.00"), _list="LEDGERENTRIES.LIST"),
                   line("CGST Output", "9.00", _list="LEDGERENTRIES.LIST"),
                   line("SGST Output", "9.00", _list="LEDGERENTRIES.LIST")],
            inventory=_inventory("100.00", inward=False)),
        vch({"DATE": "20250928", "VOUCHERTYPENAME": "Purchase", "MASTERID": "2"},
            lines=[line("Samsung", "118.00", bills=bill("P001", "New Ref", "118.00"), _list="LEDGERENTRIES.LIST"),
                   line("CGST Input", "-9.00", _list="LEDGERENTRIES.LIST"),
                   line("SGST Input", "-9.00", _list="LEDGERENTRIES.LIST")],
            inventory=_inventory("-100.00", inward=True)),
        vch({"DATE": "20251020", "VOUCHERTYPENAME": "Receipt", "MASTERID": "3"},
            lines=[line("Cash", "-118.00"), line("Apex", "118.00", bills=bill("S001", receipt_bill_type, "118.00"))]),
        vch({"DATE": "20251010", "VOUCHERTYPENAME": "Payment", "MASTERID": "4"},
            lines=[line("Samsung", "-50.00", bills=bill("P001", "Agst Ref", "-50.00")), line("HDFC", "50.00")]),
        vch({"DATE": "20251130", "VOUCHERTYPENAME": "Payment", "MASTERID": "5"},
            lines=[line("Rent", "-75.00"), line("HDFC", "75.00")]),
    ])


TDL_OK = ("<ENVELOPE><BODY><DATA><COLLECTION>" + "".join(
    f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{name}</LEDGERNAME><S0LEDGERGUID>{guid}</S0LEDGERGUID></ALLLEDGERENTRIES.LIST>"
    for name, guid in [("Cash", "g-cash"), ("Apex", "g-apex"), ("HDFC", "g-hdfc")]) + "</COLLECTION></DATA></BODY></ENVELOPE>")


async def _run(tmp_path, monkeypatch, vouchers=None, tdl=TDL_OK):
    monkeypatch.setattr(p06, "EXPECTED_PARTY_PAYMENTS", 1)
    monkeypatch.setattr(p06, "EXPECTED_EXPENSE_PAYMENTS", 1)
    fake, _ = a_tally()
    fake.route("S0P06Vouchers", lambda body: vouchers or _vouchers())
    fake.route("S0P06LineFetch", lambda body: vouchers_xml([vch({"DATE": "20251130", "VOUCHERTYPENAME": "Payment"},
                                                                lines=[line("Rent", "-75.00"), line("HDFC", "75.00")])]))
    fake.route("S0P06LineTdl", lambda body: tdl)
    fake.route("S0P06LedgerGuids", lambda body: objects_xml("LEDGER", [{"Name": n, "GUID": g} for n, g in GUIDS.items()]))
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    await run_probe(p06.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(6)["parts"]["A"]


async def test_nested_lists_balance_and_the_tdl_route_gives_ledger_guids(tmp_path, monkeypatch):
    part = await _run(tmp_path, monkeypatch)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["balancing_rule"] == "default"
    assert obs["line_guid"]["route"] == "tdl"
    assert obs["presence"]["batch"]["GODOWNNAME"] == 2
    assert "inline TDL" in part["summary"]
    assert part["fixtures"] == ["p06_A_vouchers_nested.xml", "p06_A_ledger_guids.xml", "p06_A_line_guid_fetch.xml",
                                "p06_A_line_guid_tdl.xml"]


async def test_no_ledger_guid_on_lines_is_different(tmp_path, monkeypatch):
    part = await _run(tmp_path, monkeypatch, tdl="<ENVELOPE></ENVELOPE>")
    assert part["outcome"] == "DIFFERENT"
    assert "name resolution stays" in part["spec_impact"]


async def test_unbalanced_voucher_fails(tmp_path, monkeypatch):
    part = await _run(tmp_path, monkeypatch, vouchers=_vouchers(sales_party="-117.00"))
    assert part["outcome"] == "FAILED"
    assert "Rung 0" in part["spec_impact"]


async def test_missing_bill_allocations_fail(tmp_path, monkeypatch):
    part = await _run(tmp_path, monkeypatch, vouchers=_vouchers(bills=False))
    assert part["outcome"] == "FAILED"
    assert "S1 schema" in part["spec_impact"]


async def test_bill_types_not_matching_the_seed_are_different(tmp_path, monkeypatch):
    part = await _run(tmp_path, monkeypatch, vouchers=_vouchers(receipt_bill_type="New Ref"))
    assert part["outcome"] == "DIFFERENT"
    assert part["observations"]["structure"]["receipts_agst_ref"] is False
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p03_voucher_ids_flags.py v2/tests/probes/test_p04_alterid_filter.py v2/tests/probes/test_p06_nested_lines_ledger_guid.py -q`
Expected: FAIL — `ImportError` for each new module.

- [x] **Step 3: Write `v2/probes/p03_voucher_ids_flags.py`**

```python
"""Probe 3 — voucher IDs and flags can be fetched (S0 spec §7 "Probe 3", A part). Feeds R6, R16.

The B part (cancelled / optional vouchers carry their flags) is added in plan part 3.
"""
from __future__ import annotations

import re

from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import voucher_request

FIELDS = ["GUID", "MasterID", "AlterID", "Date", "VoucherTypeName", "VoucherNumber", "Reference", "PartyLedgerName",
          "Narration", "IsCancelled", "IsOptional", "IsPostDated"]
FLAG_CANDIDATES = ("IsCancelled", "IsOptional", "IsPostDated")
EXPECTED_VOUCHERS = 50                                   # the seed company (docs/seed-data-setup.md)
INVOICE_IN_NARRATION = re.compile(r"Invoice #(?P<ref>[SP]\d{3})")


async def run_a(ctx: ProbeContext) -> PartResult:
    rows = read_objects(await ctx.send("vouchers_ids_flags", voucher_request("S0P03Vouchers", FIELDS, ctx.company_name)),
                        "VOUCHER", FIELDS)
    ids = {}
    for key in ("GUID", "MasterID", "AlterID"):
        values = [row[key] for row in rows]
        ids[key] = {"empty": sum(1 for value in values if not value), "duplicates": len(values) - len(set(values))}
    flags = {flag: {"empty": sum(1 for row in rows if not row[flag]), "yes": sum(1 for row in rows if row[flag] == "Yes")}
             for flag in FLAG_CANDIDATES}
    wrong_references = []
    for row in rows:
        if row["VoucherTypeName"] not in ("Sales", "Purchase"):
            continue
        match = INVOICE_IN_NARRATION.search(row["Narration"])
        expected = match.group("ref") if match else ""
        if row["Reference"] != expected:
            wrong_references.append({"narration": row["Narration"], "reference": row["Reference"], "expected": expected})
    ctx.observe("count", len(rows))
    ctx.observe("ids", ids)
    ctx.observe("flags", flags)
    ctx.observe("wrong_references", wrong_references)

    missing_flags = [flag for flag, entry in flags.items() if entry["empty"]]
    bad_ids = [key for key in ("GUID", "MasterID") if ids[key]["empty"] or ids[key]["duplicates"]]
    if ids["AlterID"]["empty"]:
        bad_ids.append("AlterID")
    if missing_flags or bad_ids or not rows:
        problems = ([f"flag(s) {', '.join(missing_flags)} don't export on every voucher"] if missing_flags else []) + \
                   ([f"{', '.join(bad_ids)} empty or duplicated"] if bad_ids else []) + \
                   (["no vouchers came back"] if not rows else [])
        impacts = (["R16 filtering (cancelled / optional / post-dated) is redesigned before S1."] if missing_flags
                   else []) + (["R6: vouchers can't be keyed and change-tracked by GUID / MasterID / AlterID as "
                                "designed; S1's voucher key is revisited."] if bad_ids or not rows else [])
        return PartResult(Outcome.FAILED, "; ".join(problems), spec_impact=" ".join(impacts))
    differences, impacts = [], []
    if len(rows) != EXPECTED_VOUCHERS:
        differences.append(f"{len(rows)} vouchers came back, not {EXPECTED_VOUCHERS}")
        impacts.append("The voucher collection doesn't return exactly the company's vouchers: the extractor's "
                       "completeness check (count vs CMPINFO / AltVchId) is revisited.")
    if wrong_references:
        differences.append(f"Reference ≠ the invoice number on {len(wrong_references)} Sales/Purchase voucher(s)")
        impacts.append("S1 can't take the invoice number from Reference alone; the recorded cases decide the source "
                       "(LESSONS §9).")
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences), spec_impact=" ".join(impacts))
    return PartResult(Outcome.CONFIRMED, f"{len(rows)} vouchers: GUID / MasterID unique, AlterID present, the three flags "
                                         "export everywhere, Reference = invoice number")


PROBE = Probe(
    id=3,
    name="voucher_ids_flags",
    question="Can voucher GUID / MasterID / AlterID / Reference and the cancelled / optional / post-dated flags be fetched?",
    feeds=("R6", "R16"),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0,),
)
```

- [x] **Step 4: Write `v2/probes/p04_alterid_filter.py`**

```python
"""Probe 4 — does `$AlterID > N` filter Voucher / Ledger / Group / StockItem correctly and safely? (S0 spec §7)

Feeds decision 9 and R6. Expected sets come from a full fetch of each type, compared by GUID.
"""
from __future__ import annotations

from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.reads import master_request, voucher_request

OBJECTS: dict[str, tuple[str, list[str]]] = {
    "voucher": ("Voucher", ["GUID", "AlterID", "MasterId"]),
    "ledger": ("Ledger", ["Name", "GUID", "AlterID"]),
    "group": ("Group", ["Name", "GUID", "AlterID"]),
    "stockitem": ("StockItem", ["Name", "GUID", "AlterID"]),
}
FAILED_IMPACT = "The $AlterID filter can't drive incremental sync: decision 9 uses the rolling re-pull fallback (R6)."


def _request(key: str, company: str, threshold: int | None = None) -> str:
    object_type, fields = OBJECTS[key]
    filters = [("S0P04Alt", f"$AlterID > {threshold}")] if threshold is not None else None
    name = f"S0P04{object_type}"
    if object_type == "Voucher":
        return voucher_request(name, fields, company, filters=filters)
    return master_request(name, object_type, fields, company, filters=filters)


def _alter_ids(text: str, key: str) -> dict[str, int]:
    object_type, fields = OBJECTS[key]
    out: dict[str, int] = {}
    for row in read_objects(text, object_type.upper(), fields):
        if row["GUID"] and row["AlterID"].lstrip("-").isdigit():
            out[row["GUID"]] = int(row["AlterID"])
    return out


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    checks: dict[str, dict] = {}
    wrong: list[str] = []
    for key in OBJECTS:
        text, error = await ctx.try_send(f"{key}_full", _request(key, company))
        full = _alter_ids(text, key) if text is not None else {}
        if error is not None or not full:
            checks[key] = {"error": error or "no rows with GUID + AlterID"}
            wrong.append(f"{key}_full")
            continue
        top = max(full.values())
        filters: dict[str, dict] = {}
        for suffix, threshold in (("gt_m_minus_5", top - 5), ("gt_m", top), ("gt_0", 0)):
            expected = {guid for guid, alter_id in full.items() if alter_id > threshold}
            text, error = await ctx.try_send(f"{key}_{suffix}", _request(key, company, threshold))
            got = set(_alter_ids(text, key)) if text is not None else None
            filters[suffix] = {"threshold": threshold, "expected": len(expected),
                               "got": None if got is None else len(got), "ok": got == expected, "error": error}
            if got != expected:
                wrong.append(f"{key}_{suffix}")
        checks[key] = {"rows": len(full), "max_alterid": top, "filters": filters}
    ctx.observe("checks", checks)
    try:
        await ctx.counters("cheap_read_after")
    except ProbeBlocked as exc:
        return PartResult(Outcome.FAILED, f"Tally stopped answering after the filters ({exc})",
                          spec_impact=FAILED_IMPACT + " The filter can hang Tally, so the agent never sends it.")
    if wrong:
        return PartResult(Outcome.FAILED, f"$AlterID > N gave wrong results for: {', '.join(wrong)}",
                          spec_impact=FAILED_IMPACT)
    return PartResult(Outcome.CONFIRMED, "$AlterID > N returns exactly the expected objects for Voucher, Ledger, Group "
                                         "and StockItem, and Tally answers a cheap read afterwards")


PROBE = Probe(
    id=4,
    name="alterid_filter",
    question="Does the $AlterID > N filter return exactly the right objects for each type, without upsetting Tally?",
    feeds=("decision 9", "R6"),
    parts={"A": run_a},
    requires=(0, 1),
)
```

- [x] **Step 5: Write `v2/probes/p06_nested_lines_ledger_guid.py`**

```python
"""Probe 6 — nested lines, the double-entry and sign rules, and a ledger GUID on lines (S0 spec §7 "Probe 6").

Feeds the S1 ingest rules, R5 and R9. List methods are fetched whole (AllLedgerEntries, LedgerEntries,
AllInventoryEntries), the form that returns nested lists (tests/fixtures/live_tally_debug.md).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from v2.agent.tally.xml_utils import get_text, read_objects, sanitize_xml
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import POSTING_RULES, ZERO, master_request, parse_vouchers, postings, voucher_request

VOUCHER_FIELDS = ["Date", "VoucherTypeName", "VoucherNumber", "MasterId", "PartyLedgerName", "Narration",
                  "AllLedgerEntries", "LedgerEntries", "AllInventoryEntries"]
LINE_FIELDS = ("LEDGERNAME", "AMOUNT", "ISDEEMEDPOSITIVE")
BILL_FIELDS = ("NAME", "BILLTYPE", "AMOUNT", "BILLCREDITPERIOD")
INVENTORY_FIELDS = ("STOCKITEMNAME", "ACTUALQTY", "BILLEDQTY", "RATE", "AMOUNT")
BATCH_FIELDS = ("GODOWNNAME", "BATCHNAME", "AMOUNT")
# Candidate ways to get a ledger GUID onto a voucher line (none verified; the probe records which work).
LINE_GUID_METHOD_CANDIDATES = ["AllLedgerEntries.LedgerGUID", "AllLedgerEntries.GUID", "AllLedgerEntries.LedgerMasterId"]
LINE_GUID_TAG_CANDIDATES = ("LEDGERGUID", "GUID", "LEDGERMASTERID", "MASTERID")
LINE_GUID_TDL_FIELD = "S0LedgerGuid"
EXPECTED_PARTY_PAYMENTS = 4                     # seed: PMT001/002/005/009 carry Agst Ref (docs/seed-data-setup.md)
EXPECTED_EXPENSE_PAYMENTS = 12


def _presence(vouchers: list[dict]) -> dict[str, dict[str, int]]:
    lines = [item for v in vouchers for item in v["ledger_lines"]]
    bills = [bill for item in lines for bill in item["bills"]]
    inventory = [inv for v in vouchers for inv in v["inventory"]]
    batches = [batch for inv in inventory for batch in inv["batches"]]
    return {
        "line": {f: sum(1 for item in lines if f in item["fields"]) for f in LINE_FIELDS} | {"total": len(lines)},
        "bill": {f: sum(1 for bill in bills if f in bill) for f in BILL_FIELDS} | {"total": len(bills)},
        "inventory": {f: sum(1 for inv in inventory if f in inv["fields"]) for f in INVENTORY_FIELDS}
                     | {"total": len(inventory)},
        "batch": {f: sum(1 for batch in batches if f in batch) for f in BATCH_FIELDS} | {"total": len(batches)},
    }


def _bill_types(voucher: dict) -> set[str]:
    return {bill.get("BILLTYPE", "") for item in voucher["ledger_lines"] for bill in item["bills"]}


def _structure(vouchers: list[dict]) -> dict:
    by_type: dict[str, list[dict]] = {}
    for voucher in vouchers:
        by_type.setdefault(voucher["header"].get("VOUCHERTYPENAME", ""), []).append(voucher)
    payments = by_type.get("Payment", [])
    party_payments = [v for v in payments if "Agst Ref" in _bill_types(v)]
    expense_payments = [v for v in payments if not _bill_types(v)]
    return {
        "counts": {kind: len(items) for kind, items in sorted(by_type.items())},
        "sales_new_ref": all("New Ref" in _bill_types(v) for v in by_type.get("Sales", [])),
        "purchase_new_ref": all("New Ref" in _bill_types(v) for v in by_type.get("Purchase", [])),
        "receipts_agst_ref": all("Agst Ref" in _bill_types(v) for v in by_type.get("Receipt", [])),
        "party_payments_agst_ref": len(party_payments) == EXPECTED_PARTY_PAYMENTS,
        "expense_payments_no_bills": len(expense_payments) == EXPECTED_EXPENSE_PAYMENTS,
        "sales_have_inventory": all(v["inventory"] for v in by_type.get("Sales", [])),
    }


def _balance(vouchers: list[dict]) -> dict:
    per_rule = {}
    for rule in POSTING_RULES:
        balanced = 0
        for voucher in vouchers:
            values = [value for _, value in postings(voucher, rule)]
            if values and None not in values and sum(values, ZERO) == ZERO:
                balanced += 1
        per_rule[rule] = balanced
    chosen = next((rule for rule in POSTING_RULES if vouchers and per_rule[rule] == len(vouchers)), None)
    sign_violations = [
        {"voucher": v["header"].get("MASTERID", ""), "ledger": item["fields"].get("LEDGERNAME", "")}
        for v in vouchers for item in v["ledger_lines"] + [a for inv in v["inventory"] for a in inv["accounting"]]
        if item["amount"] not in (None, ZERO)
        and (item["fields"].get("ISDEEMEDPOSITIVE") == "Yes") != (item["amount"] < ZERO)
    ]
    return {"balanced_per_rule": per_rule, "rule": chosen, "sign_violations": sign_violations}


def _line_guid_fetch_request(company: str) -> str:
    return voucher_request("S0P06LineFetch", ["Date", "MasterId", "AllLedgerEntries", *LINE_GUID_METHOD_CANDIDATES],
                           company, filters=[("S0P06Payments", '$VoucherTypeName = "Payment"')])


def _line_guid_tdl_request(company: str) -> str:
    walk = (f"\n<WALK>AllLedgerEntries</WALK>\n"
            f"<COMPUTE>{LINE_GUID_TDL_FIELD} : $GUID:Ledger:$LedgerName</COMPUTE>")
    return voucher_request("S0P06LineTdl", ["LedgerName", "Amount"], company, extra_collection_xml=walk)


def _fetched_line_guids(text: str) -> dict[str, int]:
    """How many ALLLEDGERENTRIES.LIST elements carry each candidate tag with a value."""
    root = ET.fromstring(sanitize_xml(text))
    found = {tag: 0 for tag in LINE_GUID_TAG_CANDIDATES}
    for item in root.iter("ALLLEDGERENTRIES.LIST"):
        for tag in LINE_GUID_TAG_CANDIDATES:
            if get_text(item, tag):
                found[tag] += 1
    return found


def _tdl_pairs(text: str) -> list[tuple[str, str]]:
    root = ET.fromstring(sanitize_xml(text))
    return [(get_text(el, "LEDGERNAME"), get_text(el, LINE_GUID_TDL_FIELD.upper()))
            for el in root.iter() if get_text(el, LINE_GUID_TDL_FIELD.upper())]


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    vouchers = parse_vouchers(await ctx.send("vouchers_nested", voucher_request("S0P06Vouchers", VOUCHER_FIELDS, company)))
    ledger_guids = {row["Name"]: row["GUID"] for row in read_objects(await ctx.send(
        "ledger_guids", master_request("S0P06LedgerGuids", "Ledger", ["Name", "GUID"], company)), "LEDGER", ["Name", "GUID"])}
    presence, structure, balance = _presence(vouchers), _structure(vouchers), _balance(vouchers)
    fetch_text, fetch_error = await ctx.try_send("line_guid_fetch", _line_guid_fetch_request(company))
    tdl_text, tdl_error = await ctx.try_send("line_guid_tdl", _line_guid_tdl_request(company))
    fetched = _fetched_line_guids(fetch_text) if fetch_text is not None else {}
    pairs = _tdl_pairs(tdl_text) if tdl_text is not None else []
    tdl_ok = bool(pairs) and all(ledger_guids.get(name) == guid for name, guid in pairs)
    fetch_ok = any(count > 0 for count in fetched.values())
    route = "fetch" if fetch_ok else "tdl" if tdl_ok else None
    ctx.observe("voucher_count", len(vouchers))
    ctx.observe("presence", presence)
    ctx.observe("structure", structure)
    ctx.observe("balance", balance)
    ctx.observe("balancing_rule", balance["rule"])
    ctx.observe("line_guid", {"route": route, "fetch_tags": fetched, "fetch_error": fetch_error,
                              "tdl_pairs": len(pairs), "tdl_matches_ledgers": tdl_ok, "tdl_error": tdl_error})

    missing = [name for name, ok in (("ledger lines", presence["line"]["total"] > 0),
                                     ("bill allocations", presence["bill"]["total"] > 0),
                                     ("Sales inventory lines", structure["sales_have_inventory"])) if not ok]
    if missing:
        return PartResult(Outcome.FAILED, f"Nested list(s) missing: {', '.join(missing)}",
                          spec_impact="A nested list S1 ingests doesn't export: S1 schema change before S1 "
                                      "(Part 1 §5 'Cloud' ingest rules, R5).")
    if balance["rule"] is None or balance["sign_violations"]:
        return PartResult(Outcome.FAILED, f"Lines don't balance under any posting rule ({balance['balanced_per_rule']}) "
                                          f"or a debit isn't negative ({len(balance['sign_violations'])} line(s))",
                          spec_impact="Rung 0 (Σ lines = 0.00) and the debit-negative rule can't be applied to the "
                                      "export as-is: the S1 ingest rules are revisited (Part 1 §6).")
    differences, impacts = [], []
    wrong_structure = [key for key, ok in structure.items() if key != "counts" and ok is False]
    if wrong_structure:
        differences.append(f"bill/inventory structure differs from the seed: {', '.join(wrong_structure)}")
        impacts.append("Bill allocations don't export the way S1's ingest assumes (New Ref / Agst Ref per voucher "
                       "kind); the recorded structure goes into the S1 spec.")
    if route is None:
        differences.append("no route gives a ledger GUID on voucher lines")
        impacts.append("Ledger GUID isn't available on lines: server-side name resolution stays (already designed, R9).")
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences), spec_impact=" ".join(impacts))
    how = "a plain fetch field" if route == "fetch" else "inline TDL ($GUID:Ledger:$LedgerName)"
    return PartResult(Outcome.CONFIRMED, f"Nested lines, bills and inventory export; every voucher balances under the "
                                         f"'{balance['rule']}' rule with debit negative; ledger GUID on lines via {how}",
                      spec_impact=f"S1 ingest: posting rule '{balance['rule']}'; ledger GUID on lines comes from {how}.")


PROBE = Probe(
    id=6,
    name="nested_lines_ledger_guid",
    question="Do nested lines / bills / inventory export, balance with debit negative, and can a line carry the ledger GUID?",
    feeds=("S1 ingest rules", "R5", "R9"),
    parts={"A": run_a},
    requires=(0,),
)
```

- [x] **Step 6: Register probes 3, 4 and 6** — in `v2/probes/registry.py`:

```python
    ProbeInfo(3, "voucher_ids_flags", "A+B", "B", module="v2.probes.p03_voucher_ids_flags"),
    ProbeInfo(4, "alterid_filter", "A", "B", module="v2.probes.p04_alterid_filter"),
```
```python
    ProbeInfo(6, "nested_lines_ledger_guid", "A", "B", module="v2.probes.p06_nested_lines_ledger_guid"),
```

- [x] **Step 7: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 111** (`test_p03…` 4, `test_p04…` 3, `test_p06…` 5).

---
### Task 10: Read-only probes 12 (current snapshots), 23 (GST classification, A part), 25 (masters classification, A part)

**Files:**
- Create: `v2/probes/p12_current_snapshots.py`, `v2/probes/p23_gst_due_dates.py`, `v2/probes/p25_masters_classification.py`
- Modify: `v2/probes/registry.py` (probes 12, 23, 25 `module=`)
- Test: `v2/tests/probes/test_p12_current_snapshots.py`, `v2/tests/probes/test_p23_gst_due_dates.py`,
  `v2/tests/probes/test_p25_masters_classification.py`

**Interfaces:**
- Consumes: `wrap_report`, `parse_trial_balance`, `parse_stock_summary`, `parse_bills`, `detect_error`, `read_objects`,
  `AmountParseError`, `SEED_RECEIVABLE`, `SEED_PAYABLE`, `ANCHOR_DATE`, `reads.master_request/PRIMARY_NATURE/
  PL_PRIMARY_GROUPS/ancestors/top_group/A_FY_FROM/A_FY_TO/ZERO`
- Produces:
  - `p12_current_snapshots`: `PROBE` (id 12, part "A", `requires=(0,)`), `SNAPSHOT_DATE`, `REPORTS`
  - `p23_gst_due_dates`: `PROBE` (id 23, parts {"A"}, `planned_parts=("A", "B")`, `requires=(0,)`), `GST_CANDIDATES`
  - `p25_masters_classification`: `PROBE` (id 25, parts {"A"}, `planned_parts=("A", "B")`, `requires=(0,)`),
    `GROUP_CANDIDATES`, `VOUCHER_TYPE_CANDIDATES`, `nature_from_fields(row)`

**Probe 12 (A)** — steps `tb_today`, `bs_today`, `pl_fy2025`, `stock_summary_today`, `bills_receivable_today`,
`bills_payable_today`, all at 31-03-2026 (company A's period end; Tally's own "today" in Educational mode is 1-Mar-2026,
the last voucher date — nothing lies between). These fixtures become the S1 snapshot-ingest fixtures.
**FAILED** if a report answers with a Tally error / non-XML / no data elements, or its amounts aren't plain numbers (S1
parser impact); **BLOCKED** if the bills totals ≠ the anchors (company A drifted — `reset-a`); **CONFIRMED** otherwise
(records bytes, data-element counts, stock rows, whether the TB equals probe 0's baseline).

**Probe 23 (A)** — step `gst_ledgers`: every ledger with Name, Parent and the *candidate* fields TaxType, GSTDutyHead,
TypeOfDutyTax. A candidate identifies GST ledgers when every "Duties & Taxes" ledger has a value and no other ledger shares
it. **CONFIRMED** if one does (records whether GSTDutyHead gives Central / State / Integrated Tax); **FAILED** otherwise
(spec impact: the GST tile is dropped from v1). The due-date half is part 3's B part.

**Probe 25 (A)** — steps `groups` (Name, Parent + *candidates* PrimaryGroup, _PrimaryGroup, Nature, IsRevenue,
AffectsGrossProfit, IsDeemedPositive, ReservedName) and `voucher_types` (Name + *candidates* Parent, ReservedName).
"National Creditors" must resolve to liabilities. **CONFIRMED** if a candidate field gives its nature, IsRevenue is
consistent on the primary groups, and every voucher type exports Parent or ReservedName; **DIFFERENT** if the fields are
missing but walking Parent reaches the reserved primary group (spec impact: nature by walking Parent, base type by the
parent chain — the mapping goes into the S1 spec); **FAILED** if Parent doesn't export or the walk doesn't reach a
liabilities group. (B's "Sales - GST" → Sales is part 3.)

- [x] **Step 1: Write the failing tests**

`v2/tests/probes/test_p12_current_snapshots.py`:
```python
from v2.probes import p12_current_snapshots as p12
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, bills_xml, make_harness, ready_store, stock_summary_xml, tb_xml

BASELINE = {"Capital Account": "750000.00", "Current Assets": "-750000.00"}
TB = tb_xml([("Capital Account", "", "750000.00"), ("Current Assets", "-750000.00", "")])
BS = ("<ENVELOPE><BSNAME><DSPACCNAME><DSPDISPNAME>Capital Account</DSPDISPNAME></DSPACCNAME></BSNAME>"
      "<BSAMT><BSSUBAMT></BSSUBAMT><BSMAINAMT>750000.00</BSMAINAMT></BSAMT></ENVELOPE>")
PL = ("<ENVELOPE><DSPACCNAME><DSPDISPNAME>Sales Accounts</DSPDISPNAME></DSPACCNAME>"
      "<PLAMT><PLSUBAMT></PLSUBAMT><BSMAINAMT>2057650.00</BSMAINAMT></PLAMT></ENVELOPE>")
RECEIVABLE = bills_xml([("S015", "Apex Technologies Pvt Ltd", "-62800.00"), ("S010", "Rest", "-907737.00")])
PAYABLE = bills_xml([("P001", "Samsung India Electronics", "243100.00"), ("P004", "Rest", "1591042.00")])


def _fake(tb=TB, bs=BS, receivable=RECEIVABLE):
    fake, _ = a_tally()
    fake.route("<ID>Trial Balance</ID>", lambda body: tb)
    fake.route("<ID>Balance Sheet</ID>", lambda body: bs)
    fake.route("<ID>Profit and Loss</ID>", lambda body: PL)
    fake.route("<ID>Stock Summary</ID>", lambda body: stock_summary_xml([("Electronics", "60 Nos", "", "697500.00")]))
    fake.route("<ID>Bills Receivable</ID>", lambda body: receivable)
    fake.route("<ID>Bills Payable</ID>", lambda body: PAYABLE)
    return fake


async def _run(tmp_path, fake):
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store, baseline=BASELINE)
    await run_probe(p12.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(12)["parts"]["A"]


async def test_six_snapshots_parse_and_bills_match_the_anchors(tmp_path):
    part = await _run(tmp_path, _fake())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["tb_equals_baseline"] is True
    assert part["fixtures"] == ["p12_A_tb_today.xml", "p12_A_bs_today.xml", "p12_A_pl_fy2025.xml",
                                "p12_A_stock_summary_today.xml", "p12_A_bills_receivable_today.xml",
                                "p12_A_bills_payable_today.xml"]


async def test_tb_amounts_that_are_not_plain_numbers_fail(tmp_path):
    part = await _run(tmp_path, _fake(tb=tb_xml([("Capital Account", "", "7,50,000.00 Cr")])))
    assert part["outcome"] == "FAILED"
    assert "plain numbers" in part["summary"]


async def test_a_report_answering_with_an_error_fails(tmp_path):
    part = await _run(tmp_path, _fake(bs="<ENVELOPE><LINEERROR>Report not found</LINEERROR></ENVELOPE>"))
    assert part["outcome"] == "FAILED"
    assert "Balance Sheet" in part["summary"]


async def test_bills_not_matching_the_anchors_block(tmp_path):
    part = await _run(tmp_path, _fake(receivable=bills_xml([("S015", "Apex", "-1.00")])))
    assert part["outcome"] == "BLOCKED"
    assert "reset-a" in part["summary"]
```

`v2/tests/probes/test_p23_gst_due_dates.py`:
```python
from v2.probes import p23_gst_due_dates as p23
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, make_harness, objects_xml, ready_store

HEADS = {"CGST": "Central Tax", "SGST": "State Tax", "IGST": "Integrated Tax"}


def _rows(tax_type="GST", duty=True, type_of_duty=""):
    rows = [{"Name": f"{kind} {side}", "Parent": "Duties & Taxes", "TaxType": tax_type,
             "GSTDutyHead": HEADS[kind] if duty else "", "TypeOfDutyTax": type_of_duty}
            for kind in HEADS for side in ("Input", "Output")]
    rows += [{"Name": name, "Parent": parent, "TaxType": "", "GSTDutyHead": "",
              "TypeOfDutyTax": "Others" if type_of_duty else ""}
             for name, parent in (("Cash", "Cash-in-Hand"), ("Rent", "Indirect Expenses"), ("Apex", "Sundry Debtors"))]
    return rows


async def _run(tmp_path, rows):
    fake, _ = a_tally()
    fake.route("S0P23Ledgers", lambda body: objects_xml("LEDGER", rows))
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    await run_probe(p23.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(23)


async def test_taxtype_identifies_the_gst_ledgers(tmp_path):
    entry = await _run(tmp_path, _rows())
    part = entry["parts"]["A"]
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["rule_field"] == "TaxType"
    assert part["observations"]["duty_head_ok"] is True
    assert entry["remaining"] == ["B"]


async def test_type_of_duty_tax_alone_is_enough(tmp_path):
    part = (await _run(tmp_path, _rows(tax_type="", duty=False, type_of_duty="GST")))["parts"]["A"]
    assert part["outcome"] == "CONFIRMED"
    assert part["observations"]["rule_field"] == "TypeOfDutyTax"
    assert part["observations"]["duty_head_ok"] is False


async def test_no_candidate_field_fails(tmp_path):
    part = (await _run(tmp_path, _rows(tax_type="", duty=False)))["parts"]["A"]
    assert part["outcome"] == "FAILED"
    assert "GST position tile is dropped" in part["spec_impact"]
```

`v2/tests/probes/test_p25_masters_classification.py`:
```python
from v2.probes import p25_masters_classification as p25
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, make_harness, objects_xml, ready_store

VOUCHER_TYPES = [{"Name": "Sales", "Parent": "Sales", "ReservedName": "Sales"},
                 {"Name": "Payment", "Parent": "Payment", "ReservedName": "Payment"}]


def _groups(with_fields=True, with_parent=True):
    base = [("Current Liabilities", "Primary", "Current Liabilities", "No"),
            ("Sundry Creditors", "Current Liabilities", "Current Liabilities", "No"),
            ("National Creditors", "Sundry Creditors", "Current Liabilities", "No"),
            ("Sales Accounts", "Primary", "Sales Accounts", "Yes")]
    return [{"Name": name, "Parent": parent if with_parent else "", "_PrimaryGroup": primary if with_fields else "",
             "IsRevenue": revenue if with_fields else ""} for name, parent, primary, revenue in base]


async def _run(tmp_path, groups):
    fake, _ = a_tally()
    fake.route("S0P25Groups", lambda body: objects_xml("GROUP", groups))
    fake.route("S0P25VoucherTypes", lambda body: objects_xml("VOUCHERTYPE", VOUCHER_TYPES))
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    await run_probe(p25.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(25)["parts"]["A"]


async def test_nature_and_base_type_come_from_fields(tmp_path):
    part = await _run(tmp_path, _groups())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert part["observations"]["nature_field"] == "_PrimaryGroup"
    assert part["observations"]["base_types"] == {"Sales": "Sales", "Payment": "Payment"}
    assert part["fixtures"] == ["p25_A_groups.xml", "p25_A_voucher_types.xml"]


async def test_missing_fields_fall_back_to_walking_parent(tmp_path):
    part = await _run(tmp_path, _groups(with_fields=False))
    assert part["outcome"] == "DIFFERENT"
    assert part["observations"]["walk"] == ["National Creditors", "Sundry Creditors", "Current Liabilities"]
    assert "walking Parent" in part["spec_impact"]


async def test_parent_not_exported_fails(tmp_path):
    part = await _run(tmp_path, _groups(with_fields=False, with_parent=False))
    assert part["outcome"] == "FAILED"
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p12_current_snapshots.py v2/tests/probes/test_p23_gst_due_dates.py v2/tests/probes/test_p25_masters_classification.py -q`
Expected: FAIL — `ImportError` for each new module.

- [x] **Step 3: Write `v2/probes/p12_current_snapshots.py`**

```python
"""Probe 12 — current report snapshots via SVCurrentCompany (S0 spec §7 "Probe 12"). Feeds R5.

These six fixtures become the S1 snapshot-ingest fixtures.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from v2.agent.tally.amounts import AmountParseError
from v2.agent.tally.envelopes import wrap_report
from v2.agent.tally.reports import parse_bills, parse_stock_summary, parse_trial_balance
from v2.agent.tally.xml_utils import detect_error
from v2.probes.anchors import ANCHOR_DATE, SEED_PAYABLE, SEED_RECEIVABLE
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import A_FY_FROM, A_FY_TO, ZERO

SNAPSHOT_DATE = ANCHOR_DATE     # 31-03-2026: company A's period end (Tally's Educational 'today' is 1-Mar-2026)
REPORTS: list[tuple[str, str, str, str]] = [
    ("tb_today", "Trial Balance", A_FY_FROM, SNAPSHOT_DATE),
    ("bs_today", "Balance Sheet", SNAPSHOT_DATE, SNAPSHOT_DATE),
    ("pl_fy2025", "Profit and Loss", A_FY_FROM, A_FY_TO),
    ("stock_summary_today", "Stock Summary", A_FY_FROM, SNAPSHOT_DATE),
    ("bills_receivable_today", "Bills Receivable", SNAPSHOT_DATE, SNAPSHOT_DATE),
    ("bills_payable_today", "Bills Payable", SNAPSHOT_DATE, SNAPSHOT_DATE),
]
DATA_TAG_PREFIXES = ("DSP", "BS", "PL", "BILL")


def _data_elements(text: str) -> int:
    return sum(1 for el in ET.fromstring(text).iter()
               if el.tag.startswith(DATA_TAG_PREFIXES) and (el.text or "").strip())


def _bills_total(text: str) -> Decimal | None:
    amounts = [bill["amount"] for bill in parse_bills(text)]
    return None if not amounts or any(a is None for a in amounts) else sum(amounts, ZERO)


async def run_a(ctx: ProbeContext) -> PartResult:
    texts: dict[str, str] = {}
    shapes: dict[str, dict] = {}
    unusable: list[str] = []
    for step, report, from_date, to_date in REPORTS:
        text = await ctx.send(step, wrap_report(report, from_date, to_date, ctx.company_name))
        texts[step] = text
        error = detect_error(text)
        try:
            count = _data_elements(text)
        except ET.ParseError:
            count, error = 0, error or "not XML"
        shapes[step] = {"report": report, "bytes": ctx.last_response.response_bytes, "data_elements": count,
                        "tally_error": error}
        if error or count == 0:
            unusable.append(report)
    ctx.observe("reports", shapes)
    if unusable:
        return PartResult(Outcome.FAILED, f"Unusable report response(s): {', '.join(unusable)}",
                          spec_impact=f"S1 snapshot ingest can't take {', '.join(unusable)} from TYPE=Data as it is; the "
                                      "request or parser is redone before S1 (R5).")
    try:
        tb_rows = parse_trial_balance(texts["tb_today"])
        stock_rows = parse_stock_summary(texts["stock_summary_today"])
    except AmountParseError as exc:
        return PartResult(Outcome.FAILED, f"Report amounts aren't plain numbers ({exc.raw!r})",
                          spec_impact="The S1 snapshot parsers must read Tally's amount text (e.g. Dr/Cr suffixes) "
                                      "before S1 (Part 1 §13, R5).")
    receivable = _bills_total(texts["bills_receivable_today"])
    payable = _bills_total(texts["bills_payable_today"])
    baseline = ctx.store.environment.get("company_a_tb_baseline") or {}
    tb_now = {row["account_name"]: str(row["closing_balance"]) for row in tb_rows}
    ctx.observe("tb_rows", len(tb_rows))
    ctx.observe("tb_equals_baseline", tb_now == baseline)
    ctx.observe("stock_rows", len(stock_rows))
    ctx.observe("bills_totals", {"receivable": receivable, "payable": payable})
    if receivable != SEED_RECEIVABLE or payable != SEED_PAYABLE:
        return PartResult(Outcome.BLOCKED, f"Bills totals {receivable} / {payable} ≠ the anchors {SEED_RECEIVABLE} / "
                                           f"{SEED_PAYABLE}: company A has drifted. Run `uv run --project v2 python -m "
                                           "v2.probes reset-a`, then re-run.")
    return PartResult(Outcome.CONFIRMED, f"All six reports parse ({len(tb_rows)} TB rows with Decimal amounts, "
                                         f"{len(stock_rows)} stock rows); bills totals match the anchors")


PROBE = Probe(
    id=12,
    name="current_snapshots",
    question="Do TB, BS, full-FY P&L, Stock Summary and Bills Receivable / Payable export and parse at today's date?",
    feeds=("R5", "S1 snapshot fixtures"),
    parts={"A": run_a},
    requires=(0,),
)
```

- [x] **Step 4: Write `v2/probes/p23_gst_due_dates.py`**

```python
"""Probe 23 — GST classification on ledger masters (S0 spec §7 "Probe 23", A part). Feeds the Part 3 GST tile.

The due-date / credit-period half (B part) is added in plan part 3.
"""
from __future__ import annotations

from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import master_request

GST_CANDIDATES = ["TaxType", "GSTDutyHead", "TypeOfDutyTax"]
FIELDS = ["Name", "Parent", *GST_CANDIDATES]
TAX_PARENT = "Duties & Taxes"
DUTY_HEADS = {"Central Tax", "State Tax", "Integrated Tax"}


async def run_a(ctx: ProbeContext) -> PartResult:
    rows = read_objects(await ctx.send("gst_ledgers", master_request("S0P23Ledgers", "Ledger", FIELDS, ctx.company_name)),
                        "LEDGER", FIELDS)
    tax = [row for row in rows if row["Parent"] == TAX_PARENT]
    other = [row for row in rows if row["Parent"] != TAX_PARENT]
    per_field = {field: {"tax_filled": sum(1 for row in tax if row[field]),
                         "other_filled": sum(1 for row in other if row[field]),
                         "tax_values": sorted({row[field] for row in tax if row[field]}),
                         "other_values": sorted({row[field] for row in other if row[field]})}
                 for field in GST_CANDIDATES}
    rule_field = None
    for field in GST_CANDIDATES:
        tax_values = {row[field] for row in tax}
        if tax and "" not in tax_values and not tax_values & {row[field] for row in other}:
            rule_field = field
            break
    duty_heads = sorted({row["GSTDutyHead"] for row in tax})
    duty_head_ok = bool(tax) and set(duty_heads) <= DUTY_HEADS
    ctx.observe("tax_ledgers", len(tax))
    ctx.observe("fields", per_field)
    ctx.observe("rule_field", rule_field)
    ctx.observe("duty_heads", duty_heads)
    ctx.observe("duty_head_ok", duty_head_ok)
    if rule_field is None:
        return PartResult(Outcome.FAILED, f"No candidate field ({', '.join(GST_CANDIDATES)}) identifies the "
                                          f"{len(tax)} Duties & Taxes ledgers",
                          spec_impact="Tax ledgers can't be identified without name matching: the GST position tile is "
                                      "dropped from v1, never approximated (Part 1 probe 23, Part 3).")
    head = "GSTDutyHead gives Central / State / Integrated Tax" if duty_head_ok else "GSTDutyHead doesn't give the duty head"
    return PartResult(Outcome.CONFIRMED, f"{rule_field} identifies the {len(tax)} GST ledgers "
                                         f"({per_field[rule_field]['tax_values']}); {head}",
                      spec_impact=f"S1 classifies GST ledgers by {rule_field}; "
                                  + ("duty head from GSTDutyHead." if duty_head_ok else "no duty head field (tile shows "
                                                                                        "GST in total only)."))


PROBE = Probe(
    id=23,
    name="gst_due_dates",
    question="Do ledger masters expose GST classification (and bills a due date / credit period)?",
    feeds=("Part 3 tiles",),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0,),
)
```

- [x] **Step 5: Write `v2/probes/p25_masters_classification.py`**

```python
"""Probe 25 — group nature / revenue flags and voucher-type base type (S0 spec §7 "Probe 25", A part).

Feeds the S1 schema, R5 and R16. The B part (custom voucher type "Sales - GST" → Sales) is added in plan part 3.
"""
from __future__ import annotations

from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import PL_PRIMARY_GROUPS, PRIMARY_NATURE, ancestors, master_request

GROUP_CANDIDATES = ["PrimaryGroup", "_PrimaryGroup", "Nature", "IsRevenue", "AffectsGrossProfit", "IsDeemedPositive",
                    "ReservedName"]
GROUP_FIELDS = ["Name", "Parent", *GROUP_CANDIDATES]
VOUCHER_TYPE_CANDIDATES = ["Parent", "ReservedName"]
VOUCHER_TYPE_FIELDS = ["Name", *VOUCHER_TYPE_CANDIDATES]
CHECK_GROUP = "National Creditors"


def nature_from_fields(row: dict[str, str]) -> tuple[str | None, str | None]:
    """(nature, the field that gave it) from the candidate fields alone."""
    for field in ("PrimaryGroup", "_PrimaryGroup"):
        if row.get(field) in PRIMARY_NATURE:
            return PRIMARY_NATURE[row[field]], field
    nature = row.get("Nature", "").lower()
    for word, value in (("liabilit", "liabilities"), ("asset", "assets"), ("income", "income"), ("expense", "expenses")):
        if word in nature:
            return value, "Nature"
    return None, None


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    groups = read_objects(await ctx.send("groups", master_request("S0P25Groups", "Group", GROUP_FIELDS, company)),
                          "GROUP", GROUP_FIELDS)
    vtypes = read_objects(await ctx.send("voucher_types", master_request("S0P25VoucherTypes", "VoucherType",
                                                                         VOUCHER_TYPE_FIELDS, company)),
                          "VOUCHERTYPE", VOUCHER_TYPE_FIELDS)
    parents = {row["Name"]: row["Parent"] for row in groups if row["Name"]}
    present = {field: sum(1 for row in groups if row[field]) for field in ["Parent", *GROUP_CANDIDATES]}
    check = next((row for row in groups if row["Name"] == CHECK_GROUP), None)
    walk = ancestors(CHECK_GROUP, parents) if check else []
    walk_nature = PRIMARY_NATURE.get(walk[-1]) if walk else None
    field_nature, nature_field = nature_from_fields(check) if check else (None, None)
    revenue = {row["Name"]: row["IsRevenue"] for row in groups if row["Name"] in PRIMARY_NATURE and row["IsRevenue"]}
    revenue_ok = bool(revenue) and all((value == "Yes") == (name in PL_PRIMARY_GROUPS) for name, value in revenue.items())
    vparents = {row["Name"]: row["Parent"] for row in vtypes if row["Name"]}
    base_types = {row["Name"]: row["ReservedName"] or ancestors(row["Name"], vparents)[-1] for row in vtypes}
    vtypes_ok = bool(vtypes) and all(row["Parent"] or row["ReservedName"] for row in vtypes)
    ctx.observe("present", present)
    ctx.observe("walk", walk)
    ctx.observe("walk_nature", walk_nature)
    ctx.observe("field_nature", field_nature)
    ctx.observe("nature_field", nature_field)
    ctx.observe("is_revenue_consistent", revenue_ok)
    ctx.observe("voucher_type_fields", {field: sum(1 for row in vtypes if row[field]) for field in VOUCHER_TYPE_CANDIDATES})
    ctx.observe("base_types", base_types)

    if not present["Parent"] or check is None or walk_nature != "liabilities":
        return PartResult(Outcome.FAILED, f"Group Parent doesn't classify {CHECK_GROUP!r} (walk: {walk or 'none'})",
                          spec_impact="S1 can't tell balance-sheet from P&L groups from the export: the S1 schema's "
                                      "group classification is revisited before S1 (R5, R16).")
    if field_nature == "liabilities" and revenue_ok and vtypes_ok:
        return PartResult(Outcome.CONFIRMED, f"{nature_field} gives {CHECK_GROUP!r} = liabilities; IsRevenue is "
                                             "consistent; voucher types export Parent / ReservedName",
                          spec_impact=f"S1: group nature from {nature_field}, P&L flag from IsRevenue; voucher base type "
                                      "from ReservedName, walking Parent for custom types.")
    return PartResult(Outcome.DIFFERENT, "Nature / revenue / base-type fields don't all export; walking Parent gives "
                                         f"{CHECK_GROUP!r} → {walk[-1]} ({walk_nature})",
                      spec_impact="Nature is derived by walking Parent to a reserved primary group (PRIMARY_NATURE map) "
                                  "and base type by the voucher-type Parent chain; the mapping goes into the S1 spec.")


PROBE = Probe(
    id=25,
    name="masters_classification",
    question="Do groups export nature / IsRevenue / AffectsGrossProfit, and voucher types their parent and base type?",
    feeds=("S1 schema", "R5", "R16"),
    parts={"A": run_a},
    planned_parts=("A", "B"),
    requires=(0,),
)
```

- [x] **Step 6: Register probes 12, 23 and 25** — in `v2/probes/registry.py`:

```python
    ProbeInfo(12, "current_snapshots", "A", "B", module="v2.probes.p12_current_snapshots"),
```
```python
    ProbeInfo(23, "gst_due_dates", "A+B", "B", module="v2.probes.p23_gst_due_dates"),
```
```python
    ProbeInfo(25, "masters_classification", "A+B", "B", module="v2.probes.p25_masters_classification"),
```

- [x] **Step 7: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 121** (`test_p12…` 4, `test_p23…` 3, `test_p25…` 3).

---
### Task 11: Mutating probes 7 (deleted vouchers) and 8 (ledger rename)

**Files:**
- Create: `v2/probes/p07_deleted_vouchers.py`, `v2/probes/p08_ledger_rename.py`
- Modify: `v2/probes/registry.py` (probes 7, 8 `module=`)
- Test: `v2/tests/probes/test_p07_deleted_vouchers.py`, `v2/tests/probes/test_p08_ledger_rename.py`

**Interfaces:**
- Consumes: `read_objects`, `formula_string`, `ProbeContext.send/counters/pause/on_abort/resolve_abort`, `Action`,
  `reads.voucher_request/master_request/parse_vouchers/primary_lines`, `THROWAWAY_DATE_TEXT`, `THROWAWAY_EXPENSE_LEDGER`
- Produces:
  - `p07_deleted_vouchers`: `PROBE` (id 7, part "A", `requires=(0, 1)`, mutating, educational-sensitive), `FIELDS`,
    `TOMBSTONE_CANDIDATE = "IsDeleted"`, `REFS`, `NARRATIONS`
  - `p08_ledger_rename`: `PROBE` (id 8, part "A", `requires=(0, 1)`, mutating), `LEDGER = "Rajesh Computers"`,
    `RENAMED = "Rajesh Computers S0"`

**Probe 7 (A)** — spec §7: pause `create_voucher` ("S0-throwaway 2") → `throwaway_created` (GUID, MasterId, AlterID,
Narration, Date, *candidate* IsDeleted) + counters; pause `delete_voucher` → `after_delete` (gone? tombstone?) + counters;
pause `create_voucher` ("S0-throwaway 3") → `second_throwaway` (GUID / MasterID differ from voucher 2's?); pause
`delete_voucher` → extra step `after_second_delete`. Cleanup notes cover each voucher until its delete is confirmed.
**FAILED** if a GUID is reused or a deleted voucher lingers without a tombstone flag (the deletion compare is redesigned,
R7); **DIFFERENT** if deleted vouchers come back as tombstones (IsDeleted = Yes) or only MasterIDs are reused (compare by
GUID); **BLOCKED** if a created voucher can't be found; **CONFIRMED** otherwise.

**Probe 8 (A)** — spec §7: `rename_before` (ledger GUID, AlterID) + extra steps `rename_target_absent`,
`rename_before_vouchers` (its vouchers' AlterIDs and exported names); pause `rename_ledger` to "Rajesh Computers S0" →
`rename_after` + `rename_after_vouchers` + counters; pause `rename_ledger` back → `rename_restored` +
`rename_restored_vouchers`. **FAILED** if the GUID changes on rename (R9's cascade by GUID can't work); **DIFFERENT** if
old vouchers keep the old name or their AlterIDs change (R9 adjusted as recorded); **BLOCKED** if the ledger is missing,
the target name exists, or the rename back isn't visible (cleanup note); **CONFIRMED** otherwise (vouchers export the new
name, their AlterIDs don't move, same GUID — R9's server-side cascade by GUID is right).

- [x] **Step 1: Write the failing tests**

`v2/tests/probes/test_p07_deleted_vouchers.py`:
```python
from v2.probes import p07_deleted_vouchers as p07
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, make_harness, objects_xml, ready_store


def _fake(reuse_guid=False, reuse_master_id=False, linger=None):
    fake, counters = a_tally()
    state = {"rows": [], "next": 51, "last": None, "by_ref": {}}
    fake.route("S0P07Vouchers", lambda body: objects_xml("VOUCHER", state["rows"]))

    def on_action(action):
        ref = action.params["ref"]
        if action.kind == "create_voucher":
            last = state["last"]
            master_id = last["MasterId"] if (reuse_guid or reuse_master_id) and last else str(state["next"])
            guid = last["GUID"] if reuse_guid and last else f"g-1-{state['next']:08x}"
            row = {"GUID": guid, "MasterId": master_id, "AlterID": str(100 + state["next"]),
                   "Narration": action.params["narration"], "Date": "20260331", "IsDeleted": "No"}
            state["next"] += 1
            state["rows"].append(row)
            state["by_ref"][ref] = row
            counters["AltVchId"] += 1
        else:
            row = state["by_ref"][ref]
            state["last"] = dict(row)
            counters["AltVchId"] += 3
            if linger == "tombstone":
                row["IsDeleted"] = "Yes"
            elif linger is None:
                state["rows"].remove(row)

    return fake, on_action


async def _run(tmp_path, **kw):
    fake, on_action = _fake(**kw)
    io = ScriptedIO(on_action=on_action)
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    await run_probe(p07.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return store.probe_entry(7)["parts"]["A"], io


async def test_deleted_voucher_vanishes_and_ids_are_not_reused(tmp_path):
    part, io = await _run(tmp_path)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert [a.kind for a in io.actions] == ["create_voucher", "delete_voucher", "create_voucher", "delete_voucher"]
    assert part["observations"]["counters_moved_on_delete"] is True
    assert part["fixtures"] == ["p07_A_throwaway_created.xml", "p07_A_after_delete.xml", "p07_A_second_throwaway.xml",
                                "p07_A_after_second_delete.xml"]


async def test_reused_guid_fails(tmp_path):
    part, _ = await _run(tmp_path, reuse_guid=True)
    assert part["outcome"] == "FAILED"
    assert "GUID" in part["summary"] and "R7" in part["spec_impact"]


async def test_tombstone_is_different(tmp_path):
    part, _ = await _run(tmp_path, linger="tombstone")
    assert part["outcome"] == "DIFFERENT"
    assert "tombstone" in part["spec_impact"]


async def test_voucher_lingering_without_a_flag_fails(tmp_path):
    part, _ = await _run(tmp_path, linger="plain")
    assert part["outcome"] == "FAILED"
    assert "lingers" in part["summary"]


async def test_reused_master_id_with_a_new_guid_is_different(tmp_path):
    part, _ = await _run(tmp_path, reuse_master_id=True)
    assert part["outcome"] == "DIFFERENT"
    assert "MasterID" in part["summary"]
```

`v2/tests/probes/test_p08_ledger_rename.py`:
```python
import html
import re

from v2.probes import p08_ledger_rename as p08
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, line, make_harness, objects_xml, ready_store, vch, vouchers_xml


def _fake(export_old_name=False, new_guid_on_rename=False, target_exists=False):
    fake, counters = a_tally()
    state = {"name": p08.LEDGER, "guid": "g-1-0000001e", "alter_id": 30}

    def ledger(body):
        match = re.search(r'\$Name = "([^"]*)"', body)
        wanted = html.unescape(match.group(1)) if match else ""
        rows = []
        if wanted == state["name"]:
            rows.append({"Name": state["name"], "GUID": state["guid"], "AlterID": str(state["alter_id"]),
                         "Parent": "South Zone Debtors"})
        if target_exists and wanted == p08.RENAMED:
            rows.append({"Name": p08.RENAMED, "GUID": "g-x", "AlterID": "1", "Parent": "South Zone Debtors"})
        return objects_xml("LEDGER", rows)

    def vouchers(body):
        name = p08.LEDGER if export_old_name else state["name"]
        return vouchers_xml([
            vch({"MASTERID": "6", "ALTERID": "106", "GUID": "g-v6", "PARTYLEDGERNAME": name, "DATE": "20251105"},
                lines=[line(name, "-30090.00"), line("Sales - Electronics", "30090.00")]),
            vch({"MASTERID": "13", "ALTERID": "113", "GUID": "g-v13", "PARTYLEDGERNAME": name, "DATE": "20260120"},
                lines=[line(name, "-164492.00"), line("Sales - Electronics", "164492.00")]),
            vch({"MASTERID": "8", "ALTERID": "108", "GUID": "g-v8", "PARTYLEDGERNAME": "Apex", "DATE": "20251125"},
                lines=[line("Apex", "-1.00"), line("Sales - Electronics", "1.00")]),
        ])

    fake.route("S0P08Ledger", ledger)
    fake.route("S0P08Vouchers", vouchers)

    def on_action(action):
        state["name"] = action.params["to"]
        state["alter_id"] += 1
        counters["AltMstId"] += 1
        if new_guid_on_rename:
            state["guid"] = "g-renamed"

    return fake, on_action


async def _run(tmp_path, **kw):
    fake, on_action = _fake(**kw)
    io = ScriptedIO(on_action=on_action)
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    await run_probe(p08.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return store.probe_entry(8)["parts"]["A"], io


async def test_rename_keeps_guid_and_old_vouchers_export_the_new_name(tmp_path):
    part, io = await _run(tmp_path)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["same_guid"] is True and obs["ledger_alterid_bumped"] is True
    assert obs["vouchers_export"] == "new name" and obs["voucher_alterids_changed"] is False
    assert [a.params for a in io.actions] == [
        {"company": "Bharat Traders Probe Copy", "from": p08.LEDGER, "to": p08.RENAMED},
        {"company": "Bharat Traders Probe Copy", "from": p08.RENAMED, "to": p08.LEDGER}]


async def test_old_vouchers_keeping_the_old_name_is_different(tmp_path):
    part, _ = await _run(tmp_path, export_old_name=True)
    assert part["outcome"] == "DIFFERENT"
    assert "old name" in part["summary"]


async def test_guid_changing_on_rename_fails(tmp_path):
    part, _ = await _run(tmp_path, new_guid_on_rename=True)
    assert part["outcome"] == "FAILED"
    assert "R9" in part["spec_impact"]


async def test_existing_target_name_blocks_before_any_change(tmp_path):
    part, io = await _run(tmp_path, target_exists=True)
    assert part["outcome"] == "BLOCKED"
    assert io.actions == []
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p07_deleted_vouchers.py v2/tests/probes/test_p08_ledger_rename.py -q`
Expected: FAIL — `ImportError` for each new module.

- [x] **Step 3: Write `v2/probes/p07_deleted_vouchers.py`**

```python
"""Probe 7 — a deleted voucher vanishes and its GUID is never reused (S0 spec §7 "Probe 7"). Feeds R7.

Educational-sensitive (spec §4.6); the standard-edition cross-check is deferred to tier C (spec §8).
"""
from __future__ import annotations

from v2.agent.tally.xml_utils import read_objects
from v2.probes.actions import Action
from v2.probes.companies import THROWAWAY_DATE_TEXT, THROWAWAY_EXPENSE_LEDGER
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import voucher_request

TOMBSTONE_CANDIDATE = "IsDeleted"
FIELDS = ["GUID", "MasterId", "AlterID", "Narration", "Date", TOMBSTONE_CANDIDATE]
REFS = {"v2": "p07-v2", "v3": "p07-v3"}
NARRATIONS = {"v2": "S0-throwaway 2", "v3": "S0-throwaway 3"}


def _note(narration: str) -> str:
    return f"Delete the voucher with narration {narration!r} if it still exists"


async def _read(ctx: ProbeContext, step: str) -> list[dict[str, str]]:
    return read_objects(await ctx.send(step, voucher_request("S0P07Vouchers", FIELDS, ctx.company_name)),
                        "VOUCHER", FIELDS)


def _create(ctx: ProbeContext, key: str) -> None:
    ctx.on_abort(_note(NARRATIONS[key]))
    ctx.pause(f"Create a Payment voucher dated {THROWAWAY_DATE_TEXT}: Cash → {THROWAWAY_EXPENSE_LEDGER}, ₹1, narration "
              f"{NARRATIONS[key]!r}. Save it. (company: {ctx.company_name!r})",
              Action("create_voucher", {"company": ctx.company_name, "ref": REFS[key],
                                        "ledger": THROWAWAY_EXPENSE_LEDGER, "amount": "1.00",
                                        "narration": NARRATIONS[key]}))


def _delete(ctx: ProbeContext, key: str) -> None:
    ctx.pause(f"Delete the voucher with narration {NARRATIONS[key]!r} (open it, Alt+D). (company: {ctx.company_name!r})",
              Action("delete_voucher", {"company": ctx.company_name, "ref": REFS[key]}))


def _same_voucher(rows: list[dict[str, str]], voucher: dict[str, str]) -> list[dict[str, str]]:
    return [row for row in rows if row["GUID"] == voucher["GUID"] or row["MasterId"] == voucher["MasterId"]]


async def run_a(ctx: ProbeContext) -> PartResult:
    before = await ctx.counters()
    _create(ctx, "v2")
    created = [row for row in await _read(ctx, "throwaway_created") if row["Narration"] == NARRATIONS["v2"]]
    if len(created) != 1:
        return PartResult(Outcome.BLOCKED, f"Expected one voucher {NARRATIONS['v2']!r} after the create, found "
                                           f"{len(created)}")
    v2 = created[0]
    after_create = await ctx.counters()
    _delete(ctx, "v2")
    after_delete_rows = await _read(ctx, "after_delete")
    after_delete = await ctx.counters()
    lingering = _same_voucher(after_delete_rows, v2)
    tombstone = bool(lingering) and all(row[TOMBSTONE_CANDIDATE] == "Yes" for row in lingering)
    if not lingering:
        ctx.resolve_abort(_note(NARRATIONS["v2"]))

    _create(ctx, "v3")
    third = [row for row in await _read(ctx, "second_throwaway") if row["Narration"] == NARRATIONS["v3"]]
    if len(third) != 1:
        return PartResult(Outcome.BLOCKED, f"Expected one voucher {NARRATIONS['v3']!r} after the create, found "
                                           f"{len(third)}")
    v3 = third[0]
    _delete(ctx, "v3")
    v3_lingering = [row for row in _same_voucher(await _read(ctx, "after_second_delete"), v3)
                    if row[TOMBSTONE_CANDIDATE] != "Yes"]
    if not v3_lingering:
        ctx.resolve_abort(_note(NARRATIONS["v3"]))

    guid_reused = v3["GUID"] == v2["GUID"]
    master_id_reused = v3["MasterId"] == v2["MasterId"]
    ctx.observe("voucher_2", v2)
    ctx.observe("voucher_3", v3)
    ctx.observe("counters", {"before": before.get("AltVchId"), "after_create": after_create.get("AltVchId"),
                             "after_delete": after_delete.get("AltVchId")})
    ctx.observe("counters_moved_on_delete", after_delete.get("AltVchId") != after_create.get("AltVchId"))
    ctx.observe("lingering_after_delete", lingering)
    ctx.observe("tombstone_field_present", any(row[TOMBSTONE_CANDIDATE] for row in after_delete_rows))
    ctx.observe("guid_reused", guid_reused)
    ctx.observe("master_id_reused", master_id_reused)

    failures = []
    if guid_reused:
        failures.append("the second throwaway got the deleted voucher's GUID")
    if lingering and not tombstone:
        failures.append("the deleted voucher lingers in the collection with no deleted flag")
    if v3_lingering:
        failures.append("the second deleted voucher lingers too")
    if failures:
        return PartResult(Outcome.FAILED, "; ".join(failures) + " (delete it by hand, or run reset-a)",
                          spec_impact="The deletion compare (Part 1 R7) can't rely on a GUID vanishing and never "
                                      "coming back: it is redesigned before S2.")
    if tombstone:
        return PartResult(Outcome.DIFFERENT, "A deleted voucher comes back flagged IsDeleted = Yes",
                          spec_impact="Deleted vouchers export as tombstones: the deletion compare reads the flag "
                                      "instead of absence (Part 1 R7).")
    if master_id_reused:
        return PartResult(Outcome.DIFFERENT, "The deleted voucher's MasterID was reused (with a new GUID)",
                          spec_impact="MasterIDs are reused after a delete: the deletion compare and change detection key "
                                      "on GUID only, never MasterID (Part 1 R7).")
    return PartResult(Outcome.CONFIRMED, "A deleted voucher vanishes from the collection; the next voucher gets a new "
                                         "GUID and MasterID; AltVchId moves on the delete")


PROBE = Probe(
    id=7,
    name="deleted_vouchers",
    question="Does a deleted voucher vanish, and is its GUID never reused?",
    feeds=("R7",),
    parts={"A": run_a},
    requires=(0, 1),
    mutating=True,
    educational_sensitive=True,
)
```

- [x] **Step 4: Write `v2/probes/p08_ledger_rename.py`**

```python
"""Probe 8 — what a ledger rename does to GUIDs, AlterIDs and the names old vouchers export (S0 spec §7). Feeds R9."""
from __future__ import annotations

from v2.agent.tally.envelopes import formula_string
from v2.agent.tally.xml_utils import read_objects
from v2.probes.actions import Action
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import master_request, parse_vouchers, primary_lines, voucher_request

LEDGER = "Rajesh Computers"
RENAMED = "Rajesh Computers S0"
LEDGER_FIELDS = ["Name", "GUID", "AlterID", "Parent"]
VOUCHER_FIELDS = ["GUID", "MasterId", "AlterID", "Date", "PartyLedgerName", "AllLedgerEntries", "LedgerEntries"]


async def _ledger(ctx: ProbeContext, step: str, name: str) -> dict[str, str] | None:
    xml = master_request("S0P08Ledger", "Ledger", LEDGER_FIELDS, ctx.company_name,
                         filters=[("S0P08Only", f"$Name = {formula_string(name)}")])
    rows = [row for row in read_objects(await ctx.send(step, xml), "LEDGER", LEDGER_FIELDS) if row["Name"] == name]
    return rows[0] if rows else None


async def _vouchers(ctx: ProbeContext, step: str, *, names: set[str] | None = None,
                    master_ids: set[str] | None = None) -> dict[str, dict]:
    """Vouchers referencing `names` (party or line), or the given Master IDs: MasterId → AlterID and exported names."""
    out: dict[str, dict] = {}
    for voucher in parse_vouchers(await ctx.send(step, voucher_request("S0P08Vouchers", VOUCHER_FIELDS,
                                                                       ctx.company_name))):
        header = voucher["header"]
        line_names = sorted({item["fields"].get("LEDGERNAME", "") for item in primary_lines(voucher)})
        party = header.get("PARTYLEDGERNAME", "")
        master_id = header.get("MASTERID", "")
        wanted = (master_id in master_ids) if master_ids is not None else \
            bool(names and (party in names or names & set(line_names)))
        if wanted:
            out[master_id] = {"alter_id": header.get("ALTERID", ""), "party": party, "line_names": line_names}
    return out


def _exported_name(vouchers: dict[str, dict]) -> str:
    names = {v["party"] for v in vouchers.values()} | {n for v in vouchers.values() for n in v["line_names"]}
    if RENAMED in names and LEDGER not in names:
        return "new name"
    if LEDGER in names and RENAMED not in names:
        return "old name"
    return "mixed"


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    before = await _ledger(ctx, "rename_before", LEDGER)
    if before is None:
        return PartResult(Outcome.BLOCKED, f"Ledger {LEDGER!r} isn't in {company!r}")
    if await _ledger(ctx, "rename_target_absent", RENAMED) is not None:
        return PartResult(Outcome.BLOCKED, f"A ledger {RENAMED!r} already exists (an earlier run?). Rename it back to "
                                           f"{LEDGER!r} or run reset-a, then re-run.")
    vouchers_before = await _vouchers(ctx, "rename_before_vouchers", names={LEDGER})
    if not vouchers_before:
        return PartResult(Outcome.BLOCKED, f"No vouchers reference {LEDGER!r}; nothing to observe")
    counters_before = await ctx.counters()
    note = f"Rename ledger {RENAMED!r} back to {LEDGER!r}"
    ctx.on_abort(note)
    ctx.pause(f"Rename ledger {LEDGER!r} to {RENAMED!r} (Alter → Ledger → Name) and save. (company: {company!r})",
              Action("rename_ledger", {"company": company, "from": LEDGER, "to": RENAMED}))
    after = await _ledger(ctx, "rename_after", RENAMED)
    if after is None:
        return PartResult(Outcome.BLOCKED, f"After the rename no ledger is called {RENAMED!r}")
    vouchers_after = await _vouchers(ctx, "rename_after_vouchers", master_ids=set(vouchers_before))
    counters_after = await ctx.counters()
    ctx.pause(f"Rename ledger {RENAMED!r} back to {LEDGER!r} and save. (company: {company!r})",
              Action("rename_ledger", {"company": company, "from": RENAMED, "to": LEDGER}))
    restored = await _ledger(ctx, "rename_restored", LEDGER)
    vouchers_restored = await _vouchers(ctx, "rename_restored_vouchers", master_ids=set(vouchers_before))
    if restored is None:
        return PartResult(Outcome.BLOCKED, f"The rename back to {LEDGER!r} isn't visible")
    ctx.resolve_abort(note)

    same_guid = after["GUID"] == before["GUID"] and restored["GUID"] == before["GUID"]
    alterids_changed = any(vouchers_after.get(mid, {}).get("alter_id") != v["alter_id"]
                           for mid, v in vouchers_before.items())
    exported = _exported_name(vouchers_after)
    ctx.observe("ledger", {"before": before, "after": after, "restored": restored})
    ctx.observe("same_guid", same_guid)
    ctx.observe("ledger_alterid_bumped", after["AlterID"] != before["AlterID"])
    ctx.observe("vouchers", {"before": vouchers_before, "after": vouchers_after, "restored": vouchers_restored})
    ctx.observe("vouchers_export", exported)
    ctx.observe("voucher_alterids_changed", alterids_changed)
    ctx.observe("counters_moved", {field: counters_after.get(field) != counters_before.get(field)
                                   for field in ("AltMstId", "AltVchId")})
    ctx.observe("restored_names", _exported_name(vouchers_restored))

    if not same_guid:
        return PartResult(Outcome.FAILED, "The ledger's GUID changed on rename",
                          spec_impact="R9's server-side rename cascade by GUID can't work: a rename looks like delete + "
                                      "create, and S1 re-links vouchers by name history instead.")
    differences = []
    if exported != "new name":
        differences.append(f"old vouchers export the {exported}")
    if alterids_changed:
        differences.append("old vouchers' AlterIDs changed")
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences),
                          spec_impact="R9 is adjusted: " + ("vouchers keep the name they were entered with, so the server "
                                                            "maps lines to ledgers by GUID history; " if exported != "new name"
                                                            else "") +
                                      ("a rename re-sends the vouchers through AlterID, so the server cascade is a "
                                       "safety net." if alterids_changed else "voucher AlterIDs don't move, so the "
                                                                              "server cascade by GUID stays."))
    return PartResult(Outcome.CONFIRMED, "Same ledger GUID; old vouchers export the new name; their AlterIDs don't move",
                      spec_impact="R9 holds: the server renames by ledger GUID (vouchers aren't re-sent on a rename).")


PROBE = Probe(
    id=8,
    name="ledger_rename",
    question="On a ledger rename: which name do old vouchers export, do their AlterIDs move, does the GUID stay?",
    feeds=("R9",),
    parts={"A": run_a},
    requires=(0, 1),
    mutating=True,
)
```

- [x] **Step 5: Register probes 7 and 8** — in `v2/probes/registry.py`:

```python
    ProbeInfo(7, "deleted_vouchers", "A", "B", module="v2.probes.p07_deleted_vouchers"),
    ProbeInfo(8, "ledger_rename", "A", "B", module="v2.probes.p08_ledger_rename"),
```

- [x] **Step 6: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 130** (`test_p07…` 5, `test_p08…` 4).

---
### Task 12: Probes 10 (error shapes) and 13 (backup restore, last in the A batch)

**Files:**
- Create: `v2/probes/p10_error_shapes.py`, `v2/probes/p13_backup_restore.py`
- Modify: `v2/probes/registry.py` (probes 10, 13 `module=`)
- Test: `v2/tests/probes/test_p10_error_shapes.py`, `v2/tests/probes/test_p13_backup_restore.py`

**Interfaces:**
- Consumes: `ProbeContext.try_send/send/counters/check_company/pause/on_abort/resolve_abort/run_mode`, `Action`,
  `COMPANY_PLACEHOLDER`, `esc`, `wrap_collection`, `wrap_report`, `detect_error`, `read_objects`, `LICENCE_REQUEST`,
  `parse_licence_info`, `reads.master_request/voucher_request/A_FY_FROM/A_FY_TO`, `THROWAWAY_DATE_TEXT`,
  `THROWAWAY_EXPENSE_LEDGER`
- Produces:
  - `p10_error_shapes`: `PROBE` (id 10, part "A", `requires=(0, 1, 2)`, mutating), `POPUP_TIMEOUT_S = 10.0`,
    `body_kind(text) -> str`; `observations["gate_table"]` = rows `{condition, transport, body, tally_error, snippet,
    gate_action}` for the S2 gate
  - `p13_backup_restore`: `PROBE` (id 13, part "A", `requires=(0, 1)`, mutating), `BACKUP_TAG = "p13"`, `NARRATION`,
    `VOUCHER_REF`, `AUTO_LIMIT_NOTE`

**Probe 10 (A)** — spec §7 steps, reordered **popup → no company → quit** so auto mode needs two licence clicks, not
three, and ending with Tally restarted on company A because probe 13 follows in batch 4 (the spec's "probe 10's quit
ends the batch" predates probe 13 following it):
1. pause `raise_popup` (a person: open a voucher entry screen and leave it unsaved; the operator: a duplicate stock-group
   create, LESSONS §15 rule 10) → `popup_read` (probe 2's confirmed cheap read, 10 s timeout; sidecar only on timeout) →
   pause `dismiss_popup` → `after_popup` (does Tally recover? if not, BLOCKED with a cleanup note).
2. pause `close_all_companies` → `no_company_collection` (a Ledger collection for company A), `no_company_report` (TB).
3. pause `quit_tally` → `tally_quit` (cheap read; refused → sidecar only).
4. pause `open_company` A → company guard; then, only if probe 0 recorded Educational, extra step
   `educational_licence_info` (the `$$LicenseInfo` response shape the gate can use); otherwise "not applicable".
- Output: the gate table (condition → transport result → body shape → gate action).
- **CONFIRMED** if "no company open" (collection and report) and "Tally quit" are each distinguishable from a healthy
  answer (the popup row is recorded either way — a popup that doesn't block reads is itself a finding); **DIFFERENT**
  otherwise (the gate must also check the company list, Part 1 §5 gate.py); **BLOCKED** if Tally doesn't recover after the
  popup or doesn't come back with company A.

**Probe 13 (A)** — spec §7: `before_backup` (vouchers: GUID, MasterId, Narration) + extra step `before_backup_counters`;
pause `backup_company` (a person: Tally Backup; the operator: file copy with Tally stopped) → guard; pause
`create_voucher` ("S0-throwaway 4") → `after_throwaway` (counters); pause `restore_company` → guard → `after_restore`
(vouchers) + extra step `after_restore_counters`. Records: same company GUID? counters back **below** the post-voucher
values? the throwaway gone? the 5 lowest MasterIDs and their GUIDs unchanged?
- **BLOCKED** if the throwaway is still there (the restore didn't happen — cleanup note: delete it or `reset-a`);
  **DIFFERENT** if the GUID changes (a restore = "new GUID, same name", the Q25 re-link path — Part 1 §4 updated), the
  counters don't fall back, or existing MasterIDs / GUIDs change; **CONFIRMED** otherwise.
- In auto mode the summary carries "[auto: file-level backup/restore — Tally's Backup/Restore screens not exercised]" and
  `observations["restore_method"]` says how it was done (spec §5.8 "recorded as partial").

- [x] **Step 1: Write the failing tests**

`v2/tests/probes/test_p10_error_shapes.py`:
```python
import httpx

from v2.probes import p10_error_shapes as p10
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import COMPANY_A, ScriptedIO, a_tally, make_harness, objects_xml, ready_store, tb_xml

NO_COMPANY = "<ENVELOPE><BODY><DESC><CMPINFO><COMPANY>0</COMPANY></CMPINFO></DESC></BODY></ENVELOPE>"
LICENCE = ("<ENVELOPE><HEADER><VERSION>1</VERSION><PRODMAJORREL>7</PRODMAJORREL><PRODMINORREL>0</PRODMINORREL></HEADER>"
           "<BODY><DATA><RESULT>Yes</RESULT></DATA></BODY></ENVELOPE>")


def _fake(no_company_data=False, stuck_after_popup=False):
    fake, _ = a_tally()
    state = {"popup": False}

    def cheap(body):
        if state["popup"]:
            return httpx.ReadTimeout
        return objects_xml("COMPANY", [{"Name": COMPANY_A, "GUID": "g-1"}] if fake.companies else [])

    def ledgers(body):
        if fake.companies or no_company_data:
            return objects_xml("LEDGER", [{"Name": "Cash"}])
        return NO_COMPANY

    fake.route("S0ActiveCompany", cheap)
    fake.route("S0P10Ledgers", ledgers)
    fake.route("<ID>Trial Balance</ID>",
               lambda body: tb_xml([("Capital Account", "", "1.00")]) if fake.companies else "<ENVELOPE></ENVELOPE>")
    fake.route("<TYPE>Function</TYPE>", lambda body: LICENCE)

    def on_action(action):
        if action.kind == "raise_popup":
            state["popup"] = True
        elif action.kind == "dismiss_popup":
            state["popup"] = stuck_after_popup
            fake.companies = [COMPANY_A]
        elif action.kind == "close_all_companies":
            fake.companies = []
        elif action.kind == "quit_tally":
            fake.down = True
        elif action.kind == "open_company":
            fake.down = False
            fake.companies = [COMPANY_A]

    return fake, on_action


async def _run(tmp_path, licence="educational", **kw):
    fake, on_action = _fake(**kw)
    io = ScriptedIO(on_action=on_action)
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store, licence=licence)
    store.confirm_request("active_company", 2, p10.fallback_cheap_read().replace(
        "S0P10Cheap", "S0ActiveCompany"), candidate="a")
    await run_probe(p10.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return store.probe_entry(10)["parts"]["A"], io


async def test_each_condition_has_its_own_shape(tmp_path):
    part, io = await _run(tmp_path)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    rows = {row["condition"]: row for row in part["observations"]["gate_table"]}
    assert rows["popup / modal open"]["transport"] == "timeout"
    assert rows["no company open (collection)"]["body"] == "empty"
    assert rows["Tally not running"]["transport"] == "refused"
    assert rows["Educational mode"]["body"] == "educational=True, release 7.0"
    assert [a.kind for a in io.actions] == ["raise_popup", "dismiss_popup", "close_all_companies", "quit_tally",
                                            "open_company"]
    assert part["fixtures"] == ["p10_A_popup_read.xml.json", "p10_A_after_popup.xml", "p10_A_no_company_collection.xml",
                                "p10_A_no_company_report.xml", "p10_A_tally_quit.xml.json",
                                "p10_A_educational_licence_info.xml"]


async def test_no_company_answering_with_data_is_different(tmp_path):
    part, _ = await _run(tmp_path, no_company_data=True)
    assert part["outcome"] == "DIFFERENT"
    assert "company list" in part["spec_impact"]


async def test_licensed_tally_marks_educational_not_applicable(tmp_path):
    part, _ = await _run(tmp_path, licence="licensed")
    rows = {row["condition"]: row for row in part["observations"]["gate_table"]}
    assert rows["Educational mode"]["body"] == "not applicable"
    assert "p10_A_educational_licence_info.xml" not in part["fixtures"]


async def test_tally_not_recovering_after_the_popup_blocks_with_cleanup(tmp_path):
    part, _ = await _run(tmp_path, stuck_after_popup=True)
    assert part["outcome"] == "BLOCKED"
    assert part["observations"]["cleanup_needed"] == [p10.POPUP_NOTE.format(company=COMPANY_A)]
```

`v2/tests/probes/test_p13_backup_restore.py`:
```python
import copy

from v2.probes import p13_backup_restore as p13
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import ScriptedIO, a_tally, make_harness, objects_xml, ready_store


def _fake(new_guid=False, restore_works=True):
    fake, counters = a_tally({"AltVchId": 50, "AltMstId": 266, "GUID": "g-1"})
    state = {"vouchers": [{"GUID": f"g-1-{i:08x}", "MasterId": str(i), "Narration": f"seed {i}"} for i in range(1, 8)],
             "snapshot": None}
    fake.route("S0P13Vouchers", lambda body: objects_xml("VOUCHER", state["vouchers"]))

    def on_action(action):
        if action.kind == "backup_company":
            state["snapshot"] = (copy.deepcopy(state["vouchers"]), dict(counters))
        elif action.kind == "create_voucher":
            state["vouchers"].append({"GUID": "g-1-00000033", "MasterId": "51", "Narration": action.params["narration"]})
            counters["AltVchId"] += 1
        elif action.kind == "restore_company" and restore_works:
            vouchers, saved = state["snapshot"]
            state["vouchers"] = vouchers
            counters.update(saved)
            if new_guid:
                counters["GUID"] = "g-2"

    return fake, on_action


async def _run(tmp_path, run_mode="manual", **kw):
    fake, on_action = _fake(**kw)
    io = ScriptedIO(on_action=on_action, run_mode=run_mode)
    client, store, capture = make_harness(tmp_path, fake)
    ready_store(store)
    await run_probe(p13.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return store.probe_entry(13)["parts"]["A"], io


async def test_restore_keeps_identity_and_rolls_counters_back(tmp_path):
    part, io = await _run(tmp_path)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["same_guid"] is True and obs["counters_back_below"] is True and obs["throwaway_gone"] is True
    assert obs["restore_method"] == "Tally Backup / Restore screens (manual)"
    assert [a.kind for a in io.actions] == ["backup_company", "create_voucher", "restore_company"]
    assert part["fixtures"] == ["p13_A_before_backup.xml", "p13_A_before_backup_counters.xml",
                                "p13_A_after_throwaway.xml", "p13_A_after_restore.xml",
                                "p13_A_after_restore_counters.xml"]


async def test_auto_mode_notes_the_file_level_restore(tmp_path):
    part, _ = await _run(tmp_path, run_mode="auto")
    assert part["outcome"] == "CONFIRMED"
    assert p13.AUTO_LIMIT_NOTE in part["summary"]
    assert part["observations"]["restore_method"].startswith("file copy")


async def test_new_guid_after_restore_is_different(tmp_path):
    part, _ = await _run(tmp_path, new_guid=True)
    assert part["outcome"] == "DIFFERENT"
    assert "Q25" in part["spec_impact"]


async def test_restore_that_does_not_happen_blocks_with_cleanup(tmp_path):
    part, _ = await _run(tmp_path, restore_works=False)
    assert part["outcome"] == "BLOCKED"
    assert part["observations"]["cleanup_needed"] == [p13.CLEANUP_NOTE]
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p10_error_shapes.py v2/tests/probes/test_p13_backup_restore.py -q`
Expected: FAIL — `ImportError` for each new module.

- [x] **Step 3: Write `v2/probes/p10_error_shapes.py`**

```python
"""Probe 10 — what Tally answers when something is wrong (S0 spec §7 "Probe 10"). Feeds the S2 gate (R26).

Order: popup → no company → Tally quit → back up with company A (probe 13 follows in batch 4), then the Educational row.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER, esc, wrap_collection, wrap_report
from v2.agent.tally.xml_utils import detect_error
from v2.probes.actions import Action
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.licence import LICENCE_REQUEST, parse_licence_info
from v2.probes.reads import A_FY_FROM, A_FY_TO, master_request

POPUP_TIMEOUT_S = 10.0
POPUP_NOTE = "Dismiss the popup in Tally (or restart Tally) and open company {company!r} only"
REOPEN_NOTE = "Start TallyPrime and open company {company!r} only"


def fallback_cheap_read() -> str:
    """Used only if probe 2's request isn't stored (it always is once probe 2 ran — `requires` includes 2)."""
    return wrap_collection("S0P10Cheap", "Company", ["Name", "GUID"],
                           filters=[("S0P10Active", "$Name = ##SVCurrentCompany")])


def _cheap_read(ctx: ProbeContext) -> str:
    confirmed = ctx.store.confirmed("active_company")
    template = confirmed["xml_template"] if confirmed else fallback_cheap_read()
    return template.replace(COMPANY_PLACEHOLDER, esc(ctx.company_name))


def body_kind(text: str) -> str:
    if "<ERRORMSG>" in text.upper() or detect_error(text) is not None:
        return "error message"
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return "not XML"
    has_objects = any(len(child) or child.attrib for coll in root.iter("COLLECTION") for child in coll)
    has_rows = root.find(".//DSPACCNAME") is not None or root.find(".//BILLFIXED") is not None
    return "data" if has_objects or has_rows else "empty"


def _shape(text: str | None, error: dict | None) -> dict:
    if error is not None:
        return {"transport": error["kind"], "body": "", "tally_error": None, "snippet": ""}
    return {"transport": "ok", "body": body_kind(text), "tally_error": detect_error(text), "snippet": text[:300]}


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    cheap = _cheap_read(ctx)
    popup_note, reopen_note = POPUP_NOTE.format(company=company), REOPEN_NOTE.format(company=company)

    ctx.on_abort(popup_note)
    ctx.pause("Make Tally busy with a modal: open a voucher entry screen (e.g. Vouchers → F5 Payment) and leave it open, "
              "unsaved.", Action("raise_popup", {"company": company}))
    popup = _shape(*await ctx.try_send("popup_read", cheap, timeout=POPUP_TIMEOUT_S))
    ctx.pause(f"Dismiss it (Esc, don't save) and make sure only {company!r} is open.",
              Action("dismiss_popup", {"label": ctx.part}))
    after_text, after_error = await ctx.try_send("after_popup", cheap)
    after = _shape(after_text, after_error)
    if after_error is not None:
        ctx.observe("popup", popup)
        ctx.observe("after_popup", after)
        return PartResult(Outcome.BLOCKED, f"Tally didn't recover after the popup was dismissed ({after_error['kind']})")
    ctx.resolve_abort(popup_note)

    ctx.on_abort(reopen_note)
    ctx.pause("Close every company in Tally (Alt+K → Shut Company); keep Tally running.", Action("close_all_companies"))
    collection = _shape(*await ctx.try_send("no_company_collection",
                                            master_request("S0P10Ledgers", "Ledger", ["Name"], company)))
    report = _shape(*await ctx.try_send("no_company_report", wrap_report("Trial Balance", A_FY_FROM, A_FY_TO, company)))
    ctx.pause("Quit TallyPrime completely (Ctrl+Q).", Action("quit_tally"))
    quit_shape = _shape(*await ctx.try_send("tally_quit", cheap))
    ctx.pause(f"Start TallyPrime again and open company {company!r} only.", Action("open_company", {"label": ctx.part}))
    await ctx.check_company()
    ctx.resolve_abort(reopen_note)

    if ctx.store.environment.get("licence") == "educational":
        edu_text, edu_error = await ctx.try_send("educational_licence_info", LICENCE_REQUEST)
        info = parse_licence_info(edu_text) if edu_text is not None else None
        educational = {"transport": edu_error["kind"] if edu_error else "ok",
                       "body": f"educational={info.educational}, release {info.release or '?'}" if info else "",
                       "tally_error": None, "snippet": (edu_text or "")[:300],
                       "gate_action": "flag the company 'Educational' (dates restricted); never treat as an error"}
    else:
        educational = {"transport": "", "body": "not applicable", "tally_error": None, "snippet": "",
                       "gate_action": "—"}

    table = [
        {"condition": "popup / modal open", **popup,
         "gate_action": "back off; tell the user to check Tally for an open popup (LESSONS §15 rule 10)"
                        if popup["transport"] == "timeout" else "reads still answer during this popup: the gate can't "
                                                                "see it (it only matters to writes)"},
        {"condition": "after the popup is dismissed", **after, "gate_action": "carry on"},
        {"condition": "no company open (collection)", **collection,
         "gate_action": "treat as 'company closed': skip the cycle, no alert"},
        {"condition": "no company open (report)", **report, "gate_action": "same as the collection row"},
        {"condition": "Tally not running", **quit_shape, "gate_action": "treat as 'Tally closed': skip the cycle, no alert"},
        {"condition": "Educational mode", **educational},
    ]
    ctx.observe("gate_table", table)
    blind = [row["condition"] for row in table[2:5]
             if row["transport"] == "ok" and row["body"] == "data" or
             (row["condition"] == "Tally not running" and row["transport"] != "refused")]
    if blind:
        return PartResult(Outcome.DIFFERENT, f"Not distinguishable from a healthy answer: {', '.join(blind)}",
                          spec_impact="The S2 gate can't read these conditions from the response alone: it also checks "
                                      "the company list before trusting a read (Part 1 §5 gate.py).")
    return PartResult(Outcome.CONFIRMED, "No company, no report and Tally-not-running each have their own shape "
                                         f"(popup read: {popup['transport']}); gate table recorded")


PROBE = Probe(
    id=10,
    name="error_shapes",
    question="What does Tally answer with no company open, a popup open, Tally closed, and in Educational mode?",
    feeds=("R26", "S2 gate"),
    parts={"A": run_a},
    requires=(0, 1, 2),
    mutating=True,
)
```

- [x] **Step 4: Write `v2/probes/p13_backup_restore.py`**

```python
"""Probe 13 — does a backup restore change the company GUID or MasterIDs? (S0 spec §7 "Probe 13"). Feeds R8.

Last in batch 4: it restores company A. In auto mode the backup / restore are file copies (S0-D9, spec §5.8).
"""
from __future__ import annotations

from v2.agent.tally.xml_utils import read_objects
from v2.probes.actions import Action
from v2.probes.companies import THROWAWAY_DATE_TEXT, THROWAWAY_EXPENSE_LEDGER
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.reads import voucher_request

FIELDS = ["GUID", "MasterId", "Narration"]
BACKUP_TAG = "p13"
VOUCHER_REF = "p13-v4"
NARRATION = "S0-throwaway 4"
SAMPLE = 5
CLEANUP_NOTE = f"Delete the voucher with narration {NARRATION!r} (or run `uv run --project v2 python -m v2.probes reset-a`)"
AUTO_LIMIT_NOTE = "[auto: file-level backup/restore — Tally's Backup/Restore screens not exercised]"


def _number(value: str | None) -> int | None:
    text = (value or "").strip()
    return int(text) if text.lstrip("-").isdigit() else None


async def _vouchers(ctx: ProbeContext, step: str) -> list[dict[str, str]]:
    return read_objects(await ctx.send(step, voucher_request("S0P13Vouchers", FIELDS, ctx.company_name)),
                        "VOUCHER", FIELDS)


async def run_a(ctx: ProbeContext) -> PartResult:
    company = ctx.company_name
    before_rows = await _vouchers(ctx, "before_backup")
    sample = sorted((row for row in before_rows if _number(row["MasterId"]) is not None),
                    key=lambda row: _number(row["MasterId"]))[:SAMPLE]
    before = await ctx.counters("before_backup_counters")
    ctx.pause("Back up company A: Gateway of Tally → Alt+Y (Data) → Backup, to a folder of your choice.",
              Action("backup_company", {"label": ctx.part, "tag": BACKUP_TAG}))
    await ctx.check_company()
    ctx.on_abort(CLEANUP_NOTE)
    ctx.pause(f"Create a Payment voucher dated {THROWAWAY_DATE_TEXT}: Cash → {THROWAWAY_EXPENSE_LEDGER}, ₹1, narration "
              f"{NARRATION!r}. Save it. (company: {company!r})",
              Action("create_voucher", {"company": company, "ref": VOUCHER_REF, "ledger": THROWAWAY_EXPENSE_LEDGER,
                                        "amount": "1.00", "narration": NARRATION}))
    after_throwaway = await ctx.counters("after_throwaway")
    ctx.pause(f"Close company A, restore the backup you just took over A's data folder (Alt+Y → Restore), then open "
              f"{company!r} again (only it).", Action("restore_company", {"label": ctx.part, "tag": BACKUP_TAG}))
    await ctx.check_company()
    after_rows = await _vouchers(ctx, "after_restore")
    after = await ctx.counters("after_restore_counters")

    by_master_id = {row["MasterId"]: row["GUID"] for row in after_rows}
    throwaway_gone = not any(row["Narration"] == NARRATION for row in after_rows)
    same_guid = bool(before.get("GUID")) and after.get("GUID") == before.get("GUID")
    rose = (_number(after_throwaway.get("AltVchId")) or 0) > (_number(before.get("AltVchId")) or 0)
    back_below = (_number(after.get("AltVchId")) or 0) < (_number(after_throwaway.get("AltVchId")) or 0)
    ids_kept = all(by_master_id.get(row["MasterId"]) == row["GUID"] for row in sample)
    method = ("file copy of the company folder with Tally stopped (auto)" if ctx.run_mode == "auto"
              else "Tally Backup / Restore screens (manual)")
    ctx.observe("restore_method", method)
    ctx.observe("counters", {"before": before, "after_throwaway": after_throwaway, "after_restore": after})
    ctx.observe("sample_master_ids", [row["MasterId"] for row in sample])
    ctx.observe("same_guid", same_guid)
    ctx.observe("counters_rose_on_throwaway", rose)
    ctx.observe("counters_back_below", back_below)
    ctx.observe("throwaway_gone", throwaway_gone)
    ctx.observe("master_ids_and_guids_kept", ids_kept)
    suffix = f" {AUTO_LIMIT_NOTE}" if ctx.run_mode == "auto" else ""

    if not throwaway_gone:
        return PartResult(Outcome.BLOCKED, "The throwaway voucher is still there after the restore — the restore didn't "
                                           "happen" + suffix)
    ctx.resolve_abort(CLEANUP_NOTE)
    differences, impacts = [], []
    if not same_guid:
        differences.append("the company GUID changed on restore")
        impacts.append("A restore shows up as 'new GUID, same name' (the Q25 re-link path), not restore_detected; "
                       "Part 1 §4 'Company identity changes' is updated.")
    if not back_below:
        differences.append("the counters didn't fall back below the post-change values")
        impacts.append("restore_detected can't rely on AltVchId going down; Part 1 §4 'Company identity changes' uses "
                       "another signal.")
    if not ids_kept:
        differences.append("existing vouchers' MasterIDs / GUIDs changed")
        impacts.append("R8: after a restore every voucher looks new, so the post-restore resync replaces the company's "
                       "vouchers wholesale.")
    if differences:
        return PartResult(Outcome.DIFFERENT, "; ".join(differences) + suffix, spec_impact=" ".join(impacts))
    return PartResult(Outcome.CONFIRMED, "The restore keeps the company GUID and the MasterIDs; the counters fall back "
                                         "below the post-change values; the throwaway voucher is gone" + suffix)


PROBE = Probe(
    id=13,
    name="backup_restore",
    question="After a backup restore, are the company GUID and MasterIDs the same, and do the counters fall back?",
    feeds=("R8",),
    parts={"A": run_a},
    requires=(0, 1),
    mutating=True,
)
```

- [x] **Step 5: Register probes 10 and 13** — in `v2/probes/registry.py`:

```python
    ProbeInfo(10, "error_shapes", "A", "B", module="v2.probes.p10_error_shapes"),
```
```python
    ProbeInfo(13, "backup_restore", "A", "B", module="v2.probes.p13_backup_restore"),
```

- [x] **Step 6: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass — **BASE + 138** (`test_p10…` 4, `test_p13…` 4). With BASE = 146 that is **284 passed**.

---
### Task 13: Live run (automated), results, spec + tracker updates, code review — controller steps

**Files:**
- Modify: `v2/probes/results/results.json` and `v2/tests/fixtures/sync/p{03,04,06,07,08,10,12,13,16,17,18,19,23,25}_*` +
  `p01_*` (written by the runner), `docs/bi-s0-probe-results-<date>.md` (generated), `docs/specs/2026-09-21-bi-part1-sync-design.md`,
  `docs/specs/2026-09-22-bi-s0-probes-design.md`, `docs/plans/2026-09-22-bi-part1-tracker.md`, `docs/roadmap.md` (S0 row)
- Create: `docs/code-review-bi-s0-part2-<date>.md`

These steps are for the controller with the user at the Mac (someone must click Tally's licence box). Nothing in
Tasks 1–12 touches the live Tally.

- [ ] **Step 1: Full test run**

Run: `uv run --project v2 pytest v2/tests -q 2>&1 | tail -3` and `uv run --project v2 pytest v2/tests -q -W error 2>&1 | tail -3`
Expected: all pass both times — **BASE + 138** (284 if BASE was 146). Record the count for the tracker.

- [ ] **Step 2: CLI smoke (no Tally needed)**

Run:
```bash
mkdir -p /tmp/s0-smoke-p2
uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p2/results.json list
uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p2/results.json run 5; echo "exit=$?"
uv run --project v2 python -m v2.probes --results /tmp/s0-smoke-p2/results.json run 16 --company B; echo "exit=$?"
```
Expected: 26 rows — 0–4, 6–8, 10, 12, 13, 16–19, 23, 25 "not run"; 5, 11, 14, 15, 21, 22, 24 "not built"; 9 and 20
"⏭ deferred (Q29)". `run 5` prints "not built yet", `exit=2`; `run 16 --company B` prints "Probe 16 has no part B (has A)",
`exit=2`.

- [ ] **Step 3: Isolation check against git**

Run: `git status --porcelain | grep -v -E '^\?\? (v2/|docs/)' ; git diff --stat -- . ':!docs'`
Expected: only entries that existed before this plan (see part 1 Task 9 Step 3); nothing outside `v2/` and `docs/`.

- [ ] **Step 4: Pre-flight (read-only)**

Run: `ps -axo pid,command | grep -i 'tally.exe' | grep -v grep ; curl -s --max-time 3 http://localhost:9000`
Expected: either no `tally.exe`, or one whose command line shows `/DATA:C:\users\Public\TallyPrimeEditLog\s0probe`, and
`<RESPONSE>TallyPrime Server is Running</RESPONSE>` if it runs. A `tally.exe` **without** `s0probe` in its command line is
one the operator will refuse to stop: close it by hand (or, only if it is certainly the probe Tally, add
`--stop-any-tally` to the commands below). Note in the tracker how `ps` shows the Wine command line (it decides whether
the operator recognises its Tally by argument or only by the PID it spawned).

- [ ] **Step 5: Reset company A** (clears the throwaway run's leftover EMAIL on "Electricity")

Run: `uv run --project v2 python -m v2.probes reset-a`
Expected: operator lines ending `Company A reset: a fresh copy of the seed company, renamed to 'Bharat Traders Probe Copy'.`
When `CLICK NEEDED` appears, click "T: Continue In Educational Mode" in TallyPrime. `results.json` environment gains
`company_a_reset_at`. (Probe 0's TB baseline stays valid: it is the same seed copy with the same GUID.)

- [ ] **Step 6: Re-run probe 1 (the revision)**

Run: `uv run --project v2 python -m v2.probes run 1 --auto`
Expected: `part A: CONFIRMED — AltVchId moves on every voucher change, AltMstId on every master change; …
[Educational mode — confirm on a licensed Tally]`; the previous DIFFERENT moves to `history`; the matrix shows
`alter_ledger_again`; company A keeps no "S0 Probe Ledger".

- [ ] **Step 7: The company-A batch**

Run: `uv run --project v2 python -m v2.probes run --all --auto`
Expected sequence: 0, 2, 1 "already …, skipped"; `--- anchors check (before_parity) company A: OK`; 16, 17, 18, 19; 3, 4,
6, 12, 23, 25; 7, 8, 10, 13; `--- anchors check (after_a_batch) company A: OK`; then every B / C entry "not built yet,
skipped". Expect **four** `CLICK NEEDED` prompts (probe 10: after the popup and after the quit; probe 13: after the backup
and after the restore). Probes 3, 16, 18, 23, 25 show `PARTIAL (remaining: B)` in `list`.
If the run stops:
- `Stopped: probe N part A is BLOCKED` with `CLEANUP NEEDED` — do the cleanup (or `reset-a`), fix the cause, re-run the
  same command (done parts are skipped).
- `Stopped: company A failed the anchors check` — run `reset-a`, then re-run.
- A FAILED probe stops the run too: it is a finding, not a bug — record it, then continue with
  `uv run --project v2 python -m v2.probes run <next id> --auto` for each remaining A probe in the §6 order, and finish with
  the anchors check by re-running `run --all --auto` (everything done is skipped; the two anchors steps run).

- [ ] **Step 8: Regenerate the results doc**

Run: `uv run --project v2 python -m v2.probes report`
Expected: `Wrote docs/bi-s0-probe-results-<date>.md` with `run_mode` in the environment table, one row per probe and the
last anchors checks.

- [ ] **Step 9: Write the spec consequences** (tracker rules: design consequences go into the specs, never the results doc)
  - Part 1 spec (`2026-09-21-bi-part1-sync-design.md`): one dated "Changed" line; every DIFFERENT / FAILED `spec_impact`
    applied where it points (§4 change detection and "Company identity changes", §6 rung 1 / rung 2 / quiescence guard /
    anchors, R6–R9, R16, R26, R30, decision 9 / 11); probes 16, 17, 18 written into §6 and §16 (S0 exit gate item 3),
    including probe 16's rung-1 rule sentence and as-on sentence.
  - S0 spec (`2026-09-22-bi-s0-probes-design.md`): header status (part 2 built + run); §5.8 "Limits" gains "probe 16's UI
    balance read is a later manual check"; §6 batch 4 note (probe 10 ends by reopening company A; its steps run popup →
    no company → quit); §7 probe 1 steps (throwaway ledger, second alter); §11.5 gains the extra steps listed in Tasks 5–12;
    the controller's ruling on "probe 13 recorded as partial" (see Self-review).

- [ ] **Step 10: Tracker + roadmap**
  - Tracker §3: rows 1, 3, 4, 6, 7, 8, 10, 12, 13, 16, 17, 18, 19, 23, 25 — status and proof (outcome, fixtures,
    `results.json`; "A part" where B remains); §0 S0 row ("🟡 part 2 built + run; part 3 next"); change-log entry with the
    test count; note the `ps` finding from Step 4.
  - Roadmap Set C S0 row: the same one-line status.

- [ ] **Step 11: Code review** — run the `code-review` skill on the part-2 changes under `v2/`; store findings in
  `docs/code-review-bi-s0-part2-<date>.md`; fix confirmed findings; re-run Step 1 and Step 3.

- [ ] **Step 12: Leave the Mac tidy** — Tally may stay running on `s0probe` with company A open (part 3 continues from
  there). `tally.ini` is untouched by the v2 operator; the throwaway run's edit is still saved as
  `tally.ini.before-s0` — restoring it is the user's call at the end of S0.

---

## Self-review (done while writing)

- **Spec coverage (requirement → task):**
  - S0-D9 / §5.8 automated operator: Tally control (`/DATA`, `/LOAD`, port wait, company wait through the licence box with
    `CLICK NEEDED`, timeouts tolerated while loading, `tally.ini` backed up once, data path always `s0probe`) → T3;
    company-A lifecycle `reset-a` → T3 (`company_a`) + T4 (CLI); XML writes with verified shapes, read-backs, no
    empty-value alters, "Probe"-only with the seed-rename exception → T2; `AutoOperator` implementing `ProbeIO`, every
    action logged → T4; `run --auto`, `run_mode` in results → T4 (+ per-part tag in T1); popup via duplicate-master create
    → T2/T12; probe 13 file-level restore → T3/T12; injectable process control (tests never start Wine) → T3.
  - §5.8 "Probe 1 revision" → T5 (with an end-to-end run through the real `AutoOperator` on `FakeBooks`).
  - §4.2 / §6 anchors before the parity probes and after the A batch, stop + reset hint → T1 (`run_anchor_check`,
    `ANCHORS_*` in both orders).
  - §5.1 multi-part probes (`parts={"A": run_a}` now, B later, PARTIAL until then) → T1 (`planned_parts`) + T6/T8/T9/T10.
  - §7 probes: 16 → T6; 17, 19 → T7; 18 → T8; 3, 4, 6 → T9; 12, 23, 25 → T10; 7, 8 → T11; 10, 13 → T12. Each lists its
    pauses (Actions), what it records, the outcome rules, its step names, and tier-A tests covering CONFIRMED plus at least
    one non-confirmed path.
  - §4.5 guards: reads via `ctx.send/try_send`, writes via `TallyWriter.post` (both `check_request`), mutation guard on
    every mutating probe (`mutating=True`) and in `check_writable`; cleanup notes for every throwaway in flight.
  - §11 tier-A testing: fake transport throughout; §11.1 row "probe 18 TB CONFIRMED + bills/stock FAILED → FAILED with both
    sub-verdicts" → T8 test 2; §11.3 isolation extended (probe modules never import write code) → T4.
  - Registry `module=` for every probe built → T6–T12; registry test relaxed to `part_labels` → T1.
  - Live run, results doc, spec + tracker updates, code review → T13.
- **Deliberately not in part 2 (plan part 3):** company B dataset + `setup-b` loader (§4.3, §11.4); company C (§4.4);
  probes 5, 11, 14, 15, 21, 22, 24; the B parts of 3, 16, 18, 23, 25; B/C company numbers in `OperatorConfig`
  (`open_company B` answers "plan part 3"); tier-C deferrals (9, 20, 21 timing, standard-edition 7 / 13).
- **Names used across tasks (checked):** `Action(kind, params)`, `PAUSE_KINDS`, `ASK_KINDS`;
  `ProbeContext.pause/ask(…, action)`, `ctx.run_mode`; `Probe.planned_parts/part_labels`; `run_probe`, `run_order`,
  `run_anchor_check`, `ANCHORS_BEFORE_PARITY`, `ANCHORS_AFTER_A`, `is_anchor_step`, `OrderStep`;
  `ResultsStore.record_anchor_check/anchor_checks`; `check_anchors_direct`; `THROWAWAY_DATE`, `THROWAWAY_DATE_TEXT`,
  `THROWAWAY_EXPENSE_LEDGER`; `TallyWriter` (+ `WriteRefused`, `WriteFailed`, `WriteTimeout`, `check_writable`),
  `ImportResult`, `wrap_import`, `esc`; `LICENCE_REQUEST`, `parse_licence_info`, `LicenceInfo`; `OperatorConfig`,
  `default_config`, `TallyControl`, `TallyProcess`, `ProcessRunner`, `SystemRunner`, `OperatorError`, `CLICK_NEEDED`;
  `company_a.replace_company_folder/restore_seed_copy/rename_seed_to_a/reset_company_a/backup_folder/backup_company/
  restore_company`; `AutoOperator`, `OperatorLog`, `AUTO_RUN_MODE`, `build_auto_operator`, `MANUAL_RUN_MODE`;
  `reads.*` as listed in T6; test doubles `ScriptedIO(…, on_action, answers_by_kind, run_mode)`, `FakeTally`, `a_tally`,
  `ready_store`, `vch`, `line`, `vouchers_xml`, `stock_summary_xml`, `COMPANY_A`, `FakeBooks`, `FakeRunner`, `tmp_config`,
  `sync_client`, `import_result`, `seed_state`, `write_company_folder`, `OWN_COMMAND`, `FOREIGN_COMMAND`, `STATE_FILE`.
  Action params the probes pass match what `AutoOperator` reads (T4 Interfaces list); voucher refs are unique per probe
  (`p01-v1`, `p07-v2`, `p07-v3`, `p13-v4`, `p16-future`, `p16-post-dated`, `p19-mid-capture`); fake-route collection names
  are unique and never substrings of one another (`S0P06LineFetch` / `S0P06LineTdl`, not `S0P06LineGuid…`).
- **Places where this plan departs from, or has to interpret, the spec (for the controller to rule on):**
  1. §6 says probe 10's "Tally quit" ends batch 4, yet probe 13 runs after it: probe 10 ends by reopening company A, and its
     steps run popup → no company → quit (saves one licence click).
  2. §5.8 says probe 13 is "recorded as partial" in auto mode, but PARTIAL is a probe-level outcome for missing company
     parts (§5.1, §5.4): the plan records the normal outcome plus an auto-limit note in the summary and
     `observations["restore_method"]`.
  3. Probe 16 step 5 (UI balance read) can't be automated: the operator answers empty and the probe records "not read"
     (a later manual check, like S0-D9's UI-edit parity). Step 6 can't tell "F2 date" from "FY end" on seed data (last
     voucher = Tally's current date), so the plan adds an ordinary throwaway voucher dated 31-Mar-2026.
  4. The live TB's Current Assets row has both columns positive and the six rows net to ₹33,05,800, not 0: Part 1 §6
     rung 2's "the snapshot balances (Σ ≈ 0)" assertion would fail on this export, and `parse_trial_balance`'s
     debit + credit sum for a mixed group may be wrong. Probes 16–18 treat the stock-bearing group separately and record
     both columns; probe 16 checks whether the gap equals the closing-stock value.
  5. Probe 4's "exactly the 5 highest": AlterIDs are shared across object types (AltMstId for every master), so
     `$AlterID > M-5` can hold fewer than five of one type; the plan expects "exactly the objects with AlterID > M-5".
  6. Probe 7: spec names only GUID reuse as FAILED; the plan records MasterID-only reuse as DIFFERENT (compare by GUID).
  7. Probe 10's Educational row has no method in §7; the plan records the `$$LicenseInfo` answer shape. Probe 18's Stock
     Summary uses `EXPLODEFLAG=Yes` (a probe-17 candidate) because the seed's top level shows stock groups, not items.
  8. §11.5 fixture lists grow (extra steps per task, e.g. `groups`, `vouchers_fy`, `tb_fy_end`,
     `counters_after_alter_ledger_again`, `throwaway_ledger_check`, `educational_licence_info`); `revert_ledger` goes.
  9. Candidate names that are pure guesses and may all fail: probe 17's explode variables, probe 6's line-GUID methods and
     tags and the `<WALK>/<COMPUTE>` TDL form, probe 25's `_PrimaryGroup` / `Nature`, probe 7's `IsDeleted`, the post-dated
     `ISPOSTDATED` import tag. Each failure is recorded, never guessed around.
  10. Whether `ps` shows Wine's `/DATA:` argument is unknown; the operator also recognises its Tally by the PID it
      spawned, and refuses any other Tally unless `--stop-any-tally` (T13 Step 4 records what `ps` shows).
