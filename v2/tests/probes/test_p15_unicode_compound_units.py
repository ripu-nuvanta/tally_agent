from v2.agent.tally.client import TallyClient
from v2.probes import p05_voucher_month_bounds as p05
from v2.probes import p15_unicode_compound_units as p15
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.company_b_view import HINDI_DEBTOR
from v2.probes.results import ResultsStore
from v2.probes.runner import run_probe
from v2.tests.probes.fake_books import FakeBooks, seed_company_b
from v2.tests.probes.fakes import ScriptedIO, ready_store

B = COMPANIES["B"]


def _books() -> FakeBooks:
    books = FakeBooks(name=B, educational=True)
    seed_company_b(books, "educational", masters=True)
    return books


async def _run(tmp_path, books, *, with_probe_5=True):
    store = ResultsStore(tmp_path / "results.json")
    ready_store(store, licence="educational")
    store.update_environment(company_b_loaded_at="2026-09-24T13:02:33+05:30")
    client, capture = TallyClient(transport=books.transport()), Capture(tmp_path / "fixtures")
    if with_probe_5:
        await run_probe(p05.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    await run_probe(p15.PROBE, labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    return store.probe_entry(15)["parts"]["B"]


async def test_hindi_and_compound_units_round_trip(tmp_path):
    part = await _run(tmp_path, _books())
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    # F9: on the EDUCATIONAL dataset the first Hindi-narration voucher is tag 7 (tag 2 is the licensed dataset's).
    assert obs["hindi_ledger"]["exact"] and obs["hindi_narration"]["exact"] and obs["hindi_narration"]["tag"] == 7
    # Ruling Q8: the transport form is recorded, not judged — the fake answers in UTF-8.
    assert obs["hindi_ledger"]["encoding"] == "utf-8 bytes" and obs["hindi_narration"]["encoding"] == "utf-8 bytes"
    assert obs["compound_item"]["base_units"] == "Box of 10 Nos"
    assert obs["compound_voucher"]["qty_ok"] and obs["compound_voucher"]["tag"] != obs["hindi_narration"]["tag"]
    assert obs["stock_summary"]["qty_ok"] and obs["tally_after"] == [B]
    assert part["fixtures"][-5:] == ["p15_B_hindi_ledger.xml", "p15_B_hindi_narration.xml",
                                     "p15_B_compound_unit_item.xml", "p15_B_compound_unit_voucher.xml",
                                     "p15_B_stock_summary.xml"]


def test_hindi_sent_as_character_references_is_still_exact():
    refs = "".join(f"&#{ord(c)};" for c in HINDI_DEBTOR).encode("ascii")
    check = p15.text_check(HINDI_DEBTOR, HINDI_DEBTOR, b"<NAME>" + refs + b"</NAME>")
    assert check == {"exact": True, "utf8_bytes_in_raw": False, "encoding": "character references"}


def test_mangled_hindi_is_not_exact():
    check = p15.text_check("?????", HINDI_DEBTOR, b"?????")
    assert check["exact"] is False
    assert check["encoding"] == "not in the response"        # D9: mangled text is not labelled "character references"


def test_hex_character_references_are_recognised_too():
    refs = "".join(f"&#x{ord(c):x};" for c in HINDI_DEBTOR).encode("ascii")
    assert p15.text_check(HINDI_DEBTOR, HINDI_DEBTOR, refs)["encoding"] == "character references"


async def test_the_judgement_is_on_parsed_text_whatever_the_transport_form(tmp_path):
    """Ruling Q8: a Tally that sends the Hindi as numeric character references is still CONFIRMED — "byte-exact" in
    the spec means the characters survive; the form they travelled in is recorded."""
    books = _books()
    real = books.transport()

    def to_refs(text: str) -> str:
        return "".join(c if ord(c) < 128 else f"&#{ord(c)};" for c in text)

    import httpx

    class RefsTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            response = await real.handle_async_request(request)
            body = to_refs((await response.aread()).decode("utf-8")).encode("ascii")
            return httpx.Response(response.status_code, headers={"content-type": "text/xml"}, content=body)

    books.transport = lambda: RefsTransport()
    part = await _run(tmp_path, books)
    assert part["outcome"] == "CONFIRMED", part["summary"]
    obs = part["observations"]
    assert obs["hindi_ledger"]["encoding"] == "character references"
    assert obs["hindi_narration"]["encoding"] == "character references"


async def test_without_probe_5_the_part_blocks(tmp_path):
    part = await _run(tmp_path, _books(), with_probe_5=False)
    assert part["outcome"] == "BLOCKED" and "5" in part["summary"]


async def test_a_compound_quantity_that_reads_back_wrong_fails(tmp_path):
    books = _books()
    books.edit_state(lambda s: s["items"]["A4 Paper Ream"].__setitem__("opening_qty", "150 Box"))
    part = await _run(tmp_path, books)
    assert part["outcome"] == "FAILED" and "stock summary" in part["summary"]
