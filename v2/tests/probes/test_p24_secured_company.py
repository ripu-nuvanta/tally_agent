from v2.agent.tally.client import TallyClient
from v2.probes import p02_active_company_guid as p02
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes import p24_secured_company as p24
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_c
from v2.tests.probes.fakes import ScriptedIO, mark_done, ready_store

C = COMPANIES["C"]
# Ruling S8: the throwaway credentials the fake person "types into TallyPrime". The harness never sees them; the
# credential test searches every output for these exact values (a word search for "password" can't catch a leak).
DUMMY_USERNAME = "s0dummy-user-7Qk2"
DUMMY_PASSWORD = "s0dummy-login-Zp91x"
DUMMY_VAULT_PASSWORD = "s0dummy-vault-Hr48w"
ALL_PAUSES = [p24.SECURITY_ON, p24.SECURITY_RESELECT, p24.LOGIN, p24.VAULT_ON, p24.VAULT_RESELECT, p24.VAULT_OPEN]


def _books() -> FakeBooks:
    books = FakeBooks(name=C, educational=True)
    seed_company_c(books)
    return books


def operator(books: FakeBooks, *, prompt: str = "modal", after_vault=None, after_login=None, early=None):
    """Plays the person at TallyPrime: a prompt either blocks the XML server (modal) or leaves no company open. The
    credentials go into Tally (the fake's state) only. `early` = the pause (LOGIN / VAULT_OPEN) at which the person
    presses Enter before clearing the prompt (Ruling S3)."""
    def act(text: str) -> None:
        if text == p24.SECURITY_ON:
            books.edit_state(lambda s: s.__setitem__("security", {"user": DUMMY_USERNAME, "pw": DUMMY_PASSWORD}))
        elif text == p24.VAULT_ON:
            books.edit_state(lambda s: s.__setitem__("vault", DUMMY_VAULT_PASSWORD))
        elif text in (p24.SECURITY_RESELECT, p24.VAULT_RESELECT):
            if prompt == "modal":
                books.popup = True
            else:
                books.loaded = False
        elif text in (p24.LOGIN, p24.VAULT_OPEN):
            if text == early:
                return                                   # Enter pressed while the prompt is still up
            books.popup, books.loaded = False, True
            hook = after_vault if text == p24.VAULT_OPEN else after_login
            if hook:
                hook(books)
    return act


async def _run(tmp_path, books, io, *, confirm_active=True):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    if confirm_active:
        store.confirm_request("active_company", 2, p02.CANDIDATES["a"], candidate="a")
    mark_done(store, 5, part="B")
    store.confirm_request("voucher_month", 5, p05.svdates_template(), form="svdates_typed")
    await run_probe(p24.PROBE, labels=None, client=TallyClient(transport=books.transport()), store=store,
                    capture=Capture(tmp_path / "fixtures"), io=io)
    return store.probe_entry(24)["parts"]["C"]


async def test_security_and_vault_leave_export_unchanged(tmp_path):
    books = _books()
    io = ScriptedIO(on_wait=operator(books))
    part = await _run(tmp_path, books, io)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert io.waits == ALL_PAUSES
    shapes = part["observations"]["gate_shapes"]
    assert shapes["security_login_pending"]["company_list"]["transport"] == "timeout"
    assert shapes["vault_prompt_pending"]["active_company"]["transport"] == "timeout"
    assert "No credentials" in part["spec_impact"]
    assert "p24_C_baseline_vouchers.xml" in part["fixtures"]
    assert any(f.startswith("p24_C_security_login_pending_company_list") for f in part["fixtures"])


async def test_a_prompt_that_answers_with_no_company_is_recorded(tmp_path):
    books = _books()
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, prompt="closed")))
    assert part["outcome"] == "CONFIRMED", part["summary"]
    shape = part["observations"]["gate_shapes"]["security_login_pending"]["company_list"]
    assert shape == {"transport": "answered", "body": {"companies": []}}


async def test_a_new_guid_after_the_vault_is_different_and_points_at_relink(tmp_path):
    books = _books()
    rekey = lambda b: b.edit_state(lambda s: s.__setitem__("guid", "vaulted-guid"))
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, after_vault=rekey)))
    assert part["outcome"] == "DIFFERENT" and "Q25" in part["spec_impact"]


async def test_an_empty_export_after_the_vault_fails(tmp_path):
    books = _books()
    empty = lambda b: b.edit_state(lambda s: (s["ledgers"].clear(), s["vouchers"].clear()))
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, after_vault=empty)))
    assert part["outcome"] == "FAILED" and "tallyvault" in part["summary"].lower()


async def test_another_company_open_after_login_blocks(tmp_path):
    books = _books()
    other = lambda b: b.edit_state(lambda s: (s.__setitem__("name", "Other Co"), s.__setitem__("guid", "other")))
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, after_login=other)))
    assert part["outcome"] == "BLOCKED" and "Other Co" in part["summary"]


async def test_company_c_without_setup_c_blocks(tmp_path):
    books = FakeBooks(name=C, educational=True)         # no seed_company_c: no S0 ledger, no voucher
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books)))
    assert part["outcome"] == "BLOCKED" and "setup-c" in part["summary"]


async def test_auto_mode_is_refused(tmp_path):
    books = _books()
    part = await _run(tmp_path, books, ScriptedIO(run_mode="auto"))
    assert part["outcome"] == "BLOCKED" and "manual" in part["summary"]


async def test_without_probe_2s_request_it_blocks(tmp_path):
    books = _books()
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books)), confirm_active=False)
    assert part["outcome"] == "BLOCKED" and "probe 2" in part["summary"]


async def test_probe_24_never_asks_for_or_sends_a_credential(tmp_path):
    """Ruling S8: search every output for the ACTUAL throwaway values the person typed into Tally."""
    books = _books()
    io = ScriptedIO(on_wait=operator(books))
    part = await _run(tmp_path, books, io)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    assert books.state["security"]["pw"] == DUMMY_PASSWORD and books.state["vault"] == DUMMY_VAULT_PASSWORD
    assert io.asks == []
    outputs = [f for f in (tmp_path / "fixtures").glob("p24_C_*") if f.is_file()] + [tmp_path / "results.json"]
    assert len(outputs) > 10
    texts = {f.name: f.read_text(encoding="utf-8") for f in outputs}
    texts["console"] = "\n".join(io.said + io.waits + io.asks)
    for name, text in texts.items():
        for secret in (DUMMY_USERNAME, DUMMY_PASSWORD, DUMMY_VAULT_PASSWORD):
            assert secret not in text, (name, secret)
    for request in books.requests:
        for secret in (DUMMY_USERNAME, DUMMY_PASSWORD, DUMMY_VAULT_PASSWORD):
            assert secret not in request
        assert "<PASSWORD" not in request.upper() and "<USERNAME" not in request.upper()


async def test_enter_at_login_with_the_prompt_still_open_blocks_not_fails(tmp_path):
    """Ruling S3: a person's timing is never recorded as a Tally finding."""
    books = _books()
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, early=p24.LOGIN)))
    assert part["outcome"] == "BLOCKED", part["summary"]
    assert "prompt still open" in part["summary"] and "security_on" in part["summary"]


async def test_enter_at_vault_open_with_no_company_open_blocks_not_fails(tmp_path):
    books = _books()
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, prompt="closed", early=p24.VAULT_OPEN)))
    assert part["outcome"] == "BLOCKED", part["summary"]
    assert "prompt still open" in part["summary"] and "vault_on" in part["summary"]


async def test_a_vault_rename_with_the_same_guid_is_different(tmp_path):
    """Ruling S9 (plan Ambiguity 16): a rename that keeps the GUID is recorded as DIFFERENT, not FAILED."""
    books = _books()
    rename = lambda b: b.edit_state(lambda s: s.__setitem__("name", "Probe Vault Renamed"))
    part = await _run(tmp_path, books, ScriptedIO(on_wait=operator(books, after_vault=rename)))
    assert part["outcome"] == "DIFFERENT", part["summary"]
    assert part["observations"]["sub_verdicts"] == {"security": "CONFIRMED", "TallyVault": "DIFFERENT"}
    assert "renamed" in part["summary"] and "Probe Vault Renamed" in part["summary"]
    assert "GUID" in part["spec_impact"]
