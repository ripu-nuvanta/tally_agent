import pytest

from v2.probes.actions import ASK_KINDS, PAUSE_KINDS, Action
from v2.probes.companies import COMPANIES
from v2.probes.core import ProbeBlocked
from v2.probes.operator.auto import build_auto_operator
from v2.probes.operator.tally_control import CLICK_NEEDED, OperatorError, TallyProcess
from v2.tests.probes.fake_books import OWN_COMMAND, FakeBooks, FakeRunner, tmp_config, write_company_folder

A = COMPANIES["A"]
B = COMPANIES["B"]


def _operator(tmp_path, books=None, procs=None, log_path=None, console_input=None):
    books = books or FakeBooks(name=A)
    runner = FakeRunner(books, [TallyProcess(8, OWN_COMMAND)] if procs is None else procs)
    lines: list[str] = []
    prompts: list[str] = []
    fake_console = console_input or (lambda prompt: prompts.append(prompt) or "")
    op = build_auto_operator(config=tmp_config(tmp_path), transport=books.transport(), runner=runner,
                             log_path=log_path, echo=lines.append, console_input=fake_console)
    op._prompts = prompts          # test convenience only; not part of AutoOperator's real interface
    return op, books, runner, lines


def _voucher(ref, **extra):
    return Action("create_voucher", {"company": A, "ref": ref, "ledger": "Electricity", "amount": "1.00",
                                     "narration": f"S0-throwaway {ref}", **extra})


def test_every_pause_and_ask_kind_has_a_handler(tmp_path):
    op, *_ = _operator(tmp_path)
    assert op.handled_pauses == PAUSE_KINDS
    assert op.handled_asks == ASK_KINDS


def test_a_pause_without_an_action_falls_through_to_a_console_prompt(tmp_path):
    """C18: an action-less wait (e.g. setting F2, toggling a cancelled flag) is UI-only — no XML can do it — so
    AutoOperator does not raise; it prompts whoever is at the machine, the way ConsoleIO.wait does."""
    op, *_ = _operator(tmp_path)
    op.wait("Do something clever in the UI")
    assert op._prompts == ["\n>>> Do something clever in the UI\n    Press Enter when done... "]


def test_a_pause_with_an_unhandled_action_kind_still_raises(tmp_path):
    """C18: the distinction that matters — an Action IS present but its kind isn't one `wait` handles (here, an
    ask-only kind) is a real programming error, not a legitimate human-only step, so it still raises."""
    op, *_ = _operator(tmp_path)
    with pytest.raises(OperatorError) as info:
        op.wait("Do something clever in the UI", Action("licence"))
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


def test_company_b_has_a_configured_number(tmp_path):
    assert tmp_config(tmp_path).company_numbers["B"] == "100004"


def test_open_company_b_loads_it(tmp_path):
    # C6: build our own fake for company B — the shared `_operator()` default seeds company A, so asserting B
    # against it would fail for the wrong reason.
    folder = tmp_path / "company_b_fake"
    write_company_folder(folder, B)
    books = FakeBooks(folder, name=B)
    op, books, runner, _ = _operator(tmp_path, books=books)
    op.wait("Switch Tally to company B", Action("open_company", {"label": "B"}))
    assert books.companies() == [B]


def test_setup_company_b_wraps_write_failed_as_operator_error(tmp_path):
    """F16 fix: a genuine WriteFailed reaching `setup_company_b`, driven through the real loader — not the
    'Sales - GST' preflight pause (that's CompanyBLoadError, covered separately below). Every `writer.create_*`
    call inside `load_company_b` is guarded by its own pause-and-recover logic (Ruling C11 / `_create_or_pause`,
    and the explicit try/except around `create_b_voucher`), so `fail_imports` alone never produces a raw
    WriteFailed — it gets caught and turned into CompanyBLoadError instead (see the test below). What isn't
    guarded is company_b.py's handful of plain reads (e.g. `_require_voucher_type`'s very first call,
    `writer.list_voucher_types`) — `books.popup = True` makes every request raise `httpx.ReadTimeout`, which
    `TallyWriter.post` turns into `WriteTimeout` (a `WriteFailed` subclass), and that request is the first one
    the loader makes."""
    op, books, _, _ = _operator(tmp_path)
    books.popup = True
    with pytest.raises(OperatorError, match="setup-b"):
        op.setup_company_b()


def test_setup_company_b_wraps_company_b_load_error(tmp_path):
    """The default FakeBooks has no 'Sales - GST' voucher type; the preflight pause (`_require_voucher_type`)
    doesn't create one — the fake console prompt just presses Enter — so the loader's own CompanyBLoadError
    ('still missing after the operator pause') propagates and setup_company_b wraps it."""
    op, *_ = _operator(tmp_path)
    with pytest.raises(OperatorError, match="setup-b"):
        op.setup_company_b()


# F16/F17: WriteRefused and GuardError are also named in setup_company_b's except clause, but neither is
# reachable through it without contorting the fake. WriteRefused's only raise site is check_writable(company) —
# the very first line of load_company_b — and both load_company_b's `company` default and setup_company_b's own
# signature (Ruling C3: `setup_company_b(self, licence: str = "licensed")`, no company override) are fixed to
# COMPANIES["B"], which always contains "Probe"; there is no way to feed it a non-Probe company without changing
# a signature this task's rulings fixed. GuardError's only raise sites (v2/probes/safety.py) are check_request
# (a forbidden XML pattern — none of company_b.py's own request-building ever emits one) and
# check_company/check_mutation_allowed (never called anywhere in the load_company_b path). Left uncovered
# rather than faked; see the matching comment on the `except` clause in auto.py.


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
    assert op.popup_raised is True
    op.wait("dismiss", Action("dismiss_popup", {"label": "A"}))
    assert not books.popup and books.companies() == [A]
    assert runner.spawned[-1][-1] == "/LOAD:100003"


def test_popup_not_raised_when_the_duplicate_create_succeeds(tmp_path):
    """M9: if the duplicate stock-group create doesn't time out, the popup was never actually raised."""
    books = FakeBooks(name=A)
    books._memory["stock_groups"] = []     # "Electronics" doesn't exist yet: the create succeeds instead of timing out
    op = build_auto_operator(config=tmp_config(tmp_path), transport=books.transport(),
                             runner=FakeRunner(books, [TallyProcess(8, OWN_COMMAND)]), echo=lambda line: None)
    op.wait("popup", Action("raise_popup", {"company": A}))
    assert op.popup_raised is False
    assert not books.popup


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
