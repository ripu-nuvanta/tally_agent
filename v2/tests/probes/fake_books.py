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
from decimal import Decimal
from pathlib import Path
from typing import Callable

import httpx

from v2.probes.companies import SEED_COMPANY
from v2.probes.operator.config import OperatorConfig
from v2.probes.operator.tally_control import TallyProcess
from v2.tests.probes.fakes import bills_xml, company_list_xml, objects_xml, tb_xml

# Tally's own fixed reserved-group hierarchy (not dataset-specific — just enough of it to build a believable
# Trial Balance fixture for whatever masters a test created). A bucket not listed here is already a primary
# group (e.g. "Capital Account", "Sales Accounts") and gets no separate child row.
# ASSUMPTION, not a verified read (coordinator review round 2, "noted, no action"): this hierarchy is hand-built
# Tally domain knowledge, not derived from anything the loader itself reads. It's acceptable for now because the
# group-level TB comparison is the deliberately-scoped check (ledger-level is probe 17's job, S0-D7) — but it
# must be scrutinised, not trusted, against a live Tally read the first time this loader actually runs live.
RESERVED_GROUP_PARENTS = {
    "Sundry Debtors": "Current Assets", "Bank Accounts": "Current Assets", "Cash-in-Hand": "Current Assets",
    "Sundry Creditors": "Current Liabilities", "Duties & Taxes": "Current Liabilities",
}


def _dr_cr(value: Decimal) -> tuple[str, str]:
    """Real Tally XML: a debit-natured closing balance is negative under DSPCLDRAMTA, credit-natured is
    positive under DSPCLCRAMTA (tests/fixtures/tally_samples/trial_balance_live.xml)."""
    return (f"{value:.2f}", "") if value < 0 else ("", f"{value:.2f}")

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
        "groups": {},
        "units": {},
        "items": {},
        "voucherTypes": ["Sales", "Purchase", "Receipt", "Payment", "Contra", "Journal"],
    }


def write_company_folder(folder: Path, name: str = SEED_COMPANY) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / STATE_FILE).write_text(json.dumps(seed_state(name)), encoding="utf-8")


def deemed_positive_matches(flag: str, amount: Decimal) -> bool:
    """Op 6/7/8 (docs/tally-write-exploration-v4.md): ISDEEMEDPOSITIVE=Yes always carries a NEGATIVE AMOUNT and
    No a POSITIVE one — "AMOUNT is positive on the side that grows". Every other permutation the live
    exploration tried came back EXCEPTIONS=1. A zero amount pins nothing, so it is accepted either way."""
    if amount == 0:
        return True
    return (flag == "Yes") == (amount < 0)


def import_result(created: int = 0, altered: int = 0, deleted: int = 0, errors: int = 0, last_vch_id: str = "0",
                  line_error: str = "", exceptions: int = 0) -> str:
    """The IMPORTRESULT shape TallyPrime 7 answers an import with (live 2026-09-22)."""
    err = f"<LINEERROR>{line_error}</LINEERROR>" if line_error else ""
    return ("<ENVELOPE><HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER><BODY><DATA><IMPORTRESULT>"
            f"<CREATED>{created}</CREATED><ALTERED>{altered}</ALTERED><DELETED>{deleted}</DELETED>"
            f"<LASTVCHID>{last_vch_id}</LASTVCHID><LASTMID>0</LASTMID><COMBINED>0</COMBINED><IGNORED>0</IGNORED>"
            f"<ERRORS>{errors}</ERRORS><CANCELLED>0</CANCELLED><EXCEPTIONS>{exceptions}</EXCEPTIONS>{err}"
            "</IMPORTRESULT></DATA></BODY></ENVELOPE>")


def sync_client(transport: httpx.BaseTransport) -> httpx.Client:
    return httpx.Client(base_url="http://localhost:9000", transport=transport, trust_env=False)


class FakeBooks:
    """Tally running or not, a loaded company, a licence box (`click_polls`), a busy load (`busy_polls`), a modal."""

    def __init__(self, folder: Path | None = None, *, name: str = SEED_COMPANY, running: bool = True,
                 loaded: bool = True, educational: bool = True, click_polls_on_load: int = 0,
                 busy_polls_on_load: int = 0, drop_flags: bool = False, fail_imports: bool = False):
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
        self.drop_flags = drop_flags          # a voucher import "succeeds" but ISCANCELLED/ISOPTIONAL don't stick
        # A test seam for "something changes at request N", e.g. Tally's modal appearing partway through a run:
        # called with each request body before it is answered.
        self.before_request: Callable[[str], None] | None = None
        self.fail_imports = fail_imports      # every import fails, modelling a report/company-level write refusal

    # --- company data ---------------------------------------------------------------------------------------------
    @property
    def state(self) -> dict:
        """A read-only snapshot (a copy, in both modes): callers that want to read must not accidentally mutate
        the live state by holding onto what `.state` returns. Use `edit_state` to mutate."""
        if self.folder is None:
            return copy.deepcopy(self._memory)
        return json.loads((self.folder / STATE_FILE).read_text(encoding="utf-8"))

    def edit_state(self, mutate: Callable[[dict], None]) -> None:
        """Mutate the live state and persist it — in both memory and folder-backed modes. `.state` returns a
        copy on purpose (Ruling C11/M5: a snapshot that silently discards `books.state[...] = ...` is a trap —
        it bit test setup code once already), so test setup and 'something vanished behind our back' scenarios
        go through this instead: `books.edit_state(lambda s: s["groups"].__setitem__(name, {...}))`."""
        state = self.state
        mutate(state)
        self._save(state)

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
            if self.before_request is not None:
                self.before_request(body)
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
        if "S0OpLedger" in body or "S0OneLedger" in body or "S0SignCheckOpening" in body:
            match = re.search(r'\$Name = "([^"]*)"', body)
            wanted = html.unescape(match.group(1)) if match else ""
            led = state["ledgers"].get(wanted)
            rows = [] if led is None else [{"Name": wanted, "Parent": led["parent"], "Email": led["email"],
                                            "GUID": led["guid"], "AlterID": str(led["alter_id"]),
                                            "OpeningBalance": led.get("opening", "0.00")}]
            return objects_xml("LEDGER", rows)
        if "S0BGroups" in body:
            return objects_xml("GROUP", [{"Name": n, "Parent": g["parent"]} for n, g in state["groups"].items()])
        if "S0BUnits" in body:
            return objects_xml("UNIT", [{"Name": n, "Base": u["base"] or "", "Conversion": u["conversion"] or ""}
                                        for n, u in state["units"].items()])
        if "S0BItems" in body:
            return objects_xml("STOCKITEM", [{"Name": n, "Parent": i["parent"], "BaseUnits": i["base_units"]}
                                             for n, i in state["items"].items()])
        if "S0BLedgers" in body:
            return objects_xml("LEDGER", [{"Name": n, "Parent": led["parent"]} for n, led in state["ledgers"].items()])
        if "S0BVouchers" in body:
            return objects_xml("VOUCHER", [{"MasterId": mid, "Narration": v["narration"], "Date": v["date"],
                                            "IsPostDated": v["post_dated"], "IsCancelled": v["cancelled"],
                                            "IsOptional": v["optional"]} for mid, v in state["vouchers"].items()])
        if "S0BVoucherTypes" in body:
            return objects_xml("VOUCHERTYPE", [{"Name": n} for n in state["voucherTypes"]])
        if "<ID>Trial Balance</ID>" in body:
            return tb_xml(self._trial_balance_rows(state))
        if "<ID>Bills Receivable</ID>" in body:
            return bills_xml(state.get("bills_receivable", []))
        return "<ENVELOPE></ENVELOPE>"

    def _bucket_of(self, state: dict, ledger_parent: str) -> str:
        """One hop through a custom group this fake was asked to create (e.g. National Creditors -> Sundry
        Creditors); anything else is already at the reserved-group granularity."""
        group = state["groups"].get(ledger_parent)
        return group["parent"] if group else ledger_parent

    def _trial_balance_rows(self, state: dict) -> list[tuple[str, str, str]]:
        """An exploded-to-two-levels Trial Balance (EXPLODEFLAG=Yes shape, probe 17), computed from whatever
        ledgers/groups/vouchers this fake actually has on record — not from any dataset's idea of what should
        be there. Real Tally XML signs a debit-natured closing balance negative and a credit-natured one
        positive (verified against tests/fixtures/tally_samples/trial_balance_live.xml); `_dr_cr` mirrors that.

        C30 (overturns F11/C21): a ledger's `OPENINGBALANCE` on record is SIGNED exactly as it came over the wire,
        and real Tally reads that sign — negative = Dr, positive = Cr — whatever the parent group (company A's
        abs()'d bank openings landed as credits). So this fake takes the sign as given and never re-derives it
        from the group's nature.
        """
        balances = {name: Decimal(led.get("opening", "0.00")) for name, led in state["ledgers"].items()}
        for voucher in state["vouchers"].values():
            for line in voucher.get("lines", []):
                name = line["ledger"]
                balances[name] = balances.get(name, Decimal("0.00")) + Decimal(line["amount"] or "0.00")
        buckets: dict[str, Decimal] = {}
        for name, led in state["ledgers"].items():
            bucket = self._bucket_of(state, led["parent"])
            buckets[bucket] = buckets.get(bucket, Decimal("0.00")) + balances.get(name, Decimal("0.00"))
        primaries: dict[str, Decimal] = {}
        for bucket, value in buckets.items():
            primary = RESERVED_GROUP_PARENTS.get(bucket, bucket)
            primaries[primary] = primaries.get(primary, Decimal("0.00")) + value
        rows = list(primaries.items())
        rows += [(bucket, value) for bucket, value in buckets.items()
                if RESERVED_GROUP_PARENTS.get(bucket, bucket) != bucket]
        return [(name, *_dr_cr(value)) for name, value in rows]

    def _import(self, body: str, request: httpx.Request) -> str:
        if self.fail_imports:
            return import_result(errors=1, line_error="fake import failure")
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
        if element.tag == "GROUP" and action == "Create":
            return self._create_master(state, "groups", element, request,
                                        lambda el: {"parent": el.findtext("PARENT", "")})
        if element.tag == "UNIT" and action == "Create":
            first, second = element.findtext("BASEUNITS"), element.findtext("ADDITIONALUNITS")
            if first is not None and first == second:
                # C31: the live answer to BASEUNITS=ADDITIONALUNITS=Nos (logs/setup-b-live-2026-09-24.log).
                return import_result(exceptions=1, line_error="Next Unit already contains the First unit!")
            missing = [u for u in (first, second) if u is not None and u not in state["units"]]
            if missing:                              # the fake's own wording — no live answer recorded for this
                return import_result(exceptions=1, line_error=f"fake: unit {missing[0]!r} does not exist")
            return self._create_master(state, "units", element, request,
                                        lambda el: {"base": el.findtext("BASEUNITS"),
                                                    "additional": el.findtext("ADDITIONALUNITS"),
                                                    "conversion": el.findtext("CONVERSION")})
        if element.tag == "STOCKITEM" and action == "Create":
            return self._create_master(state, "items", element, request,
                                        lambda el: {"parent": el.findtext("PARENT", ""),
                                                    "base_units": el.findtext("BASEUNITS", "")})
        return import_result(errors=1, line_error=f"fake: unsupported {element.tag}")

    def _create_master(self, state: dict, collection: str, element: ET.Element, request: httpx.Request,
                       fields: Callable[[ET.Element], dict]) -> str:
        """Shared CREATE handling for GROUP / UNIT / STOCKITEM: duplicate names raise the modal (LESSONS §15 rule 10).

        UNIT (Op 1, live-verified) carries no NAME attribute, only a <NAME> child — fall back to it, and to
        NAME.LIST/NAME for the NAME.LIST-wrapped shapes, so this generic handler keys on whatever the real
        TallyPrime import actually names the master by.
        """
        name = element.get("NAME") or element.findtext("NAME") or element.findtext("NAME.LIST/NAME") or ""
        store = state[collection]
        if name in store:
            self.popup = True
            raise httpx.ReadTimeout("duplicate master modal", request=request)
        store[name] = fields(element)
        state["alt_mst"] += 1
        self._save(state)
        return import_result(created=1)

    def _ledger(self, state: dict, element: ET.Element, action: str, request: httpx.Request) -> str:
        name = element.get("NAME", "")
        ledgers = state["ledgers"]
        if action == "Create":
            if name in ledgers:
                self.popup = True
                raise httpx.ReadTimeout("duplicate master modal", request=request)
            state["alt_mst"] += 1
            ledgers[name] = {"parent": element.findtext("PARENT", ""), "email": "", "alter_id": state["alt_mst"],
                             "guid": f"{state['guid']}-{state['alt_mst']:08x}",
                             "opening": element.findtext("OPENINGBALANCE", "0.00")}
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

    @staticmethod
    def _signed_entries(element: ET.Element):
        """Every element carrying an ISDEEMEDPOSITIVE/AMOUNT pair: the ledger lines, each inventory row, and
        each inventory row's ACCOUNTINGALLOCATIONS child (where the Task-6 I1 defect actually lived)."""
        for tag in ("ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST"):
            for entry in element.findall(tag):
                yield entry.findtext("LEDGERNAME", ""), entry
        for inv in element.findall("ALLINVENTORYENTRIES.LIST"):
            name = inv.findtext("STOCKITEMNAME", "")
            yield name, inv
            for allocation in inv.findall("ACCOUNTINGALLOCATIONS.LIST"):
                yield f"{name} (accounting allocation)", allocation

    def _signs_agree(self, element: ET.Element) -> bool:
        for _name, entry in self._signed_entries(element):
            amount = entry.findtext("AMOUNT")
            if amount is None:
                continue
            if not deemed_positive_matches(entry.findtext("ISDEEMEDPOSITIVE", "No"), Decimal(amount or "0.00")):
                return False
        return True

    def _voucher(self, state: dict, element: ET.Element, action: str) -> str:
        vouchers = state["vouchers"]
        if action == "Create":
            if not self._signs_agree(element):
                # I5: the flag whose wrong value is the documented cause of EXCEPTIONS=1 used not to be stored
                # here at all, so no balance assertion could ever see it. The fake now approximates Tally's
                # ACCEPTANCE rule instead of echoing whatever it was given: EXCEPTIONS=1 and no LINEERROR, which
                # is exactly what the live exploration got for every wrong permutation (v4 doc, cross-cutting
                # finding 2 — "there's no helpful error message").
                return import_result(exceptions=1)
            mid = str(state["next_master_id"])
            state["next_master_id"] += 1
            date = element.findtext("DATE", "")
            cancelled = "No" if self.drop_flags else (element.findtext("ISCANCELLED") or "No")
            optional = "No" if self.drop_flags else (element.findtext("ISOPTIONAL") or "No")
            lines = [{"ledger": entry.findtext("LEDGERNAME", ""), "amount": entry.findtext("AMOUNT", "0.00"),
                      "deemed_positive": entry.findtext("ISDEEMEDPOSITIVE", "No")}
                     for tag in ("ALLLEDGERENTRIES.LIST", "LEDGERENTRIES.LIST") for entry in element.findall(tag)]
            vouchers[mid] = {"narration": element.findtext("NARRATION", ""), "date": date,
                             "post_dated": element.findtext("ISPOSTDATED") or "No",
                             "cancelled": cancelled, "optional": optional, "lines": lines}
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
                 hide_args: bool = False, appears_during_wait: TallyProcess | None = None):
        self.books = books
        self.procs = list(procs or [])
        self.stubborn = stubborn          # terminate() doesn't stop it; kill() does
        self.hide_args = hide_args        # `ps` shows only the exe path, not /DATA:…
        self.appears_during_wait = appears_during_wait   # a process that shows up the first time sleep() is called
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
        if self.appears_during_wait is not None:
            self.procs.append(self.appears_during_wait)
            self.appears_during_wait = None

    def now(self) -> float:
        return self.clock
