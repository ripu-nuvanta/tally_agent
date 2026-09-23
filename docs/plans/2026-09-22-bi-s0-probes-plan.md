# S0 Probes — Part 1 of 3: v2 foundation + probes 0, 2, 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Tick each box in this file as soon as that step is verified** — not at the end (tracker rules).

**Goal:** Build the `v2/` scaffold, the copied Tally read code, the probe harness + runner, and probes 0, 2 and 1
(the prerequisites every other probe reads from), all tested at tier A with a fake Tally.

**Architecture:** A self-contained `v2` package beside the current code. `v2/agent/tally/` holds copies of the
current Tally read code with the Part 1 §13 gaps fixed. `v2/probes/` is a runner (`python -m v2.probes`) plus one
module per probe; each probe part talks to Tally through a `ProbeContext` that guards, captures and records.

**Tech Stack:** Python ≥ 3.12, httpx (async + `MockTransport` for tests), pytest + pytest-asyncio, uv.

**Spec:** [`docs/specs/2026-09-22-bi-s0-probes-design.md`](../specs/2026-09-22-bi-s0-probes-design.md)
(parent: [`2026-09-21-bi-part1-sync-design.md`](../specs/2026-09-21-bi-part1-sync-design.md) §5, §12).
**Tracker:** [`2026-09-22-bi-part1-tracker.md`](2026-09-22-bi-part1-tracker.md) §3.

**Plan parts:**
- **Part 1 (this file):** foundation + probes 0, 2, 1.
- **Part 2 (later file):** company-A probes 3, 4, 6, 7, 8, 10, 12, 13, 16–19, 23, 25 (A parts) + the anchors step in `--all`.
- **Part 3 (later file):** company-B dataset + `setup-b` loader, B / C probes 5, 11, 14, 15, 21, 22, 24 and the B parts.
- Then the live run with you at the Tally UI, results, spec updates, code review.

## Global Constraints

- **Nothing outside `v2/` and `docs/` is created or changed.** No edits to `backend/`, `frontend/`, `tests/`,
  `scripts/`, `backend/db/migrations/`, root `pyproject.toml`, root `.gitignore`.
- **v2 never imports** `backend`, `scripts` or `tests`; `v2/agent/` never imports `v2.probes`.
- Every copied file's **first line** is `# Copied from: <source path> @ c04d7d2`, second line starts `# Changes:`.
- Money is `Decimal`, never float; a missing amount is `None`, never `0`.
- No request may contain `*` as a `NATIVEMETHOD`/`FETCH` value or `$$InDateRange`.
- One request at a time; default timeout 30 s, max 90 s; no automatic retries.
- Commands run from the repo root (`/Users/nuvanta-mac-3/work/Tally prime`):
  - tests: `uv run --project v2 pytest v2/tests -q`
  - runner: `uv run --project v2 python -m v2.probes …`
- **No git commits** in this plan (the user commits when they choose).

---

### Task 1: v2 scaffold + isolation test

**Files:**
- Create: `v2/pyproject.toml`, `v2/README.md`, `v2/__init__.py`, `v2/agent/__init__.py`,
  `v2/agent/tally/__init__.py`, `v2/probes/__init__.py`, `v2/tests/__init__.py`, `v2/tests/probes/__init__.py`
- Test: `v2/tests/test_isolation.py`

**Interfaces:**
- Produces: package `v2` importable from the repo root; `violations(root: Path) -> list[str]` in the test module.

- [x] **Step 1: Create `v2/pyproject.toml`**

```toml
[project]
name = "tally-bi-v2"
version = "0.0.1"
description = "BI Part 1 (syncing) built as v2 beside the current code — see docs/specs/2026-09-21-bi-part1-sync-design.md §5."
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
pythonpath = [".."]
```

- [x] **Step 2: Create the package `__init__.py` files**

`v2/__init__.py`:
```python
"""BI Part 1 (syncing), built as v2 beside the current code. Nothing here imports backend/, tests/ or scripts/."""
```
`v2/agent/__init__.py`:
```python
"""The sync agent (S2). Only read code lives here — never write code, never v2.probes."""
```
`v2/agent/tally/__init__.py`:
```python
"""Tally read code: copies of backend/tally_bridge read paths with the Part 1 §13 gaps fixed."""
```
`v2/probes/__init__.py`:
```python
"""S0 live-Tally probes: runner, harness and one module per probe."""
```
`v2/tests/__init__.py` and `v2/tests/probes/__init__.py`: empty files.

- [x] **Step 3: Create `v2/README.md`**

```markdown
# v2 — BI Part 1 (syncing)

Built **beside** the current code. Specs: `docs/specs/2026-09-21-bi-part1-sync-design.md` (§5 "Code isolation (v2)")
and `docs/specs/2026-09-22-bi-s0-probes-design.md`. Status: `docs/plans/2026-09-22-bi-part1-tracker.md`.

## Isolation rules
- Nothing outside `v2/` (and `docs/`) is changed for Part 1.
- v2 never imports `backend`, `scripts` or `tests`. What it needs is **copied** into v2 and fixed there.
  Each copied file starts with `# Copied from: <path> @ <commit>`.
- `v2/agent/` never imports `v2.probes` (the agent ships with no write code).
- `v2/tests/test_isolation.py` enforces the import rules.

## Commands (run from the repo root)
- Tests: `uv run --project v2 pytest v2/tests -q`
- Probes: `uv run --project v2 python -m v2.probes list | run <id> | run --first | run --all | report`
```

- [x] **Step 4: Write the failing isolation test** — `v2/tests/test_isolation.py`

```python
"""Part 1 §5 "Code isolation (v2)": v2 never imports current code, and the agent never imports probes."""
from __future__ import annotations

import ast
from pathlib import Path

V2_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TOP_LEVEL = {"backend", "scripts", "tests"}


def imported_modules(source: str) -> list[str]:
    """Absolute imports in `source`; `from a import b` yields both 'a' and 'a.b'."""
    names: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
            names.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def violations(root: Path) -> list[str]:
    found: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if ".venv" in path.parts:
            continue
        rel = path.relative_to(root)
        modules = imported_modules(path.read_text(encoding="utf-8"))
        for top in sorted({m.split(".")[0] for m in modules} & FORBIDDEN_TOP_LEVEL):
            found.append(f"{rel}: imports {top}")
        if rel.parts[:1] == ("agent",) and any(m == "v2.probes" or m.startswith("v2.probes.") for m in modules):
            found.append(f"{rel}: agent imports v2.probes")
    return found


def test_v2_tree_has_no_forbidden_imports():
    assert violations(V2_ROOT) == []


def test_scanner_flags_each_forbidden_shape(tmp_path):
    (tmp_path / "agent").mkdir()
    (tmp_path / "a.py").write_text("import backend.tally_bridge.client\n")
    (tmp_path / "b.py").write_text("from scripts import seed_tally_data\n")
    (tmp_path / "c.py").write_text("from tests.fixtures import x\n")
    (tmp_path / "agent" / "d.py").write_text("from v2.probes.setup import import_xml\n")
    (tmp_path / "agent" / "e.py").write_text("from v2 import probes\n")
    (tmp_path / "ok.py").write_text("import httpx\nfrom v2.agent.tally import client\nfrom . import sibling\n")

    found = violations(tmp_path)

    assert found == [
        "a.py: imports backend",
        "agent/d.py: agent imports v2.probes",
        "agent/e.py: agent imports v2.probes",
        "b.py: imports scripts",
        "c.py: imports tests",
    ]
```

- [x] **Step 5: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: `2 passed` (uv creates `v2/.venv` and `v2/uv.lock` on first run; `.venv` is already git-ignored).

- [x] **Step 6: Tick Task 1 in the tracker** — `docs/plans/2026-09-22-bi-part1-tracker.md` §3 row "`v2/` scaffold" → 🟡
  (it becomes ✅ when Task 2 lands the copied client), Proof: `v2/tests/test_isolation.py` 2 passed.

---

### Task 2: Copied Tally read code — exceptions, xml_utils, envelopes, client

**Files:**
- Create: `v2/agent/tally/exceptions.py`, `v2/agent/tally/xml_utils.py`, `v2/agent/tally/envelopes.py`, `v2/agent/tally/client.py`
- Create: `v2/tests/fixtures/tally_samples/` (copies of 6 current fixtures) + `v2/tests/fixtures/tally_samples/SOURCE.md`
- Test: `v2/tests/agent/__init__.py` (empty), `v2/tests/agent/test_xml_utils.py`, `v2/tests/agent/test_envelopes.py`,
  `v2/tests/agent/test_client.py`, `v2/tests/test_copied_headers.py`

**Interfaces:**
- Produces:
  - `exceptions`: `TallyConnectionError`, `TallyTimeoutError(TallyConnectionError)`, `TallyResponseError`
  - `xml_utils`: `sanitize_xml(str) -> str`, `detect_error(str) -> str | None`, `get_text(Element, str) -> str`,
    `parse_company_list(str) -> list[str]`, `read_objects(raw_xml: str, tag: str, fields: list[str]) -> list[dict[str, str]]`
  - `envelopes`: `COMPANY_PLACEHOLDER = "__COMPANY__"`, `esc(str) -> str`, `formula_string(str) -> str`,
    `wrap_collection(collection_name, object_type, native_methods, company=None, *, static_vars=None, filters=None, extra_collection_xml="", extra_tdl_xml="") -> str`,
    `wrap_report(report_id, from_date, to_date, company=None, extra_vars=None) -> str`, `build_company_list() -> str`
  - `client`: `TallyResponse(text: str, raw: bytes, elapsed_ms: int)` with `.response_bytes`,
    `TallyClient(host="localhost", port=9000, transport=None)` with `async post_xml(xml, timeout=None) -> TallyResponse`,
    `async close()`, `async health_check() -> bool`; constants `DEFAULT_TIMEOUT_S = 30.0`, `MAX_TIMEOUT_S = 90.0`

- [x] **Step 1: Copy the sample fixtures (read-only source)**

Run:
```bash
mkdir -p v2/tests/fixtures/tally_samples v2/tests/agent
cp tests/fixtures/trial_balance_live.xml tests/fixtures/bills_receivable_live.xml tests/fixtures/bills_payable_live.xml \
   tests/fixtures/stock_summary_live.xml tests/fixtures/ledger_list.xml tests/fixtures/company_list_live.xml \
   v2/tests/fixtures/tally_samples/
touch v2/tests/agent/__init__.py
```
Create `v2/tests/fixtures/tally_samples/SOURCE.md`:
```markdown
Copied from `tests/fixtures/` @ c04d7d2 for v2 parser tests. These are the **NUVANTA** company's data
(e.g. party "HCODE TECHNOLOGIES"), not the seed company — parser tests only, never seed-parity anchors.
`ledger_list.xml` is a generated mock fixture.
```

- [x] **Step 2: Write the failing tests**

`v2/tests/agent/test_xml_utils.py`:
```python
from pathlib import Path

from v2.agent.tally.xml_utils import detect_error, parse_company_list, read_objects, sanitize_xml

SAMPLES = Path(__file__).resolve().parents[1] / "fixtures" / "tally_samples"


def test_company_list_live_skips_cmpinfo_counter():
    xml = (SAMPLES / "company_list_live.xml").read_text(encoding="utf-8")
    assert parse_company_list(xml) == ["NUVANTA AI TECHNOLOGIES PRIVATE LIMITED"]


def test_company_list_reads_name_child_and_name_attribute():
    xml = (
        "<ENVELOPE><CMPINFO><COMPANY>2</COMPANY></CMPINFO>"
        '<COMPANY NAME="Alpha &amp; Co"><X/></COMPANY>'
        "<COMPANY><NAME>Beta</NAME></COMPANY></ENVELOPE>"
    )
    assert parse_company_list(xml) == ["Alpha & Co", "Beta"]


def test_sanitize_strips_control_character_references():
    assert sanitize_xml("<A>x&#4;y</A>") == "<A>xy</A>"


def test_detect_error_finds_lineerror_and_error_count():
    assert detect_error("<ENVELOPE><LINEERROR>Bad date</LINEERROR></ENVELOPE>") == "Bad date"
    assert detect_error("<ENVELOPE><ERRORS>2</ERRORS></ENVELOPE>") == "Tally reported 2 error(s)"
    assert detect_error("<ENVELOPE><ERRORS>0</ERRORS></ENVELOPE>") is None
    assert detect_error("not xml") == "Invalid XML response from Tally"


def test_read_objects_reads_fields_any_case_and_skips_bare_counters():
    xml = (
        "<ENVELOPE><CMPINFO><COMPANY>0</COMPANY></CMPINFO><COLLECTION>"
        '<COMPANY NAME="Beta"><GUID TYPE="String">g-1</GUID><ALTVCHID> 12</ALTVCHID></COMPANY>'
        "</COLLECTION></ENVELOPE>"
    )
    rows = read_objects(xml, "COMPANY", ["Name", "GUID", "AltVchId", "AltMstId"])
    assert rows == [{"Name": "Beta", "GUID": "g-1", "AltVchId": "12", "AltMstId": ""}]
```

`v2/tests/agent/test_envelopes.py`:
```python
import xml.etree.ElementTree as ET

import pytest

from v2.agent.tally.envelopes import build_company_list, esc, formula_string, wrap_collection, wrap_report

NAMES = ["A & B", "Sharma & Sons' Probe Traders", 'He said "x"', "a<b>c", "शर्मा ट्रेडर्स"]


@pytest.mark.parametrize("name", NAMES)
def test_collection_escapes_company(name):
    root = ET.fromstring(wrap_collection("C1", "Ledger", ["Name"], company=name))
    assert root.find(".//SVCurrentCompany").text == name


@pytest.mark.parametrize("name", NAMES)
def test_report_escapes_company(name):
    root = ET.fromstring(wrap_report("Trial Balance", "01-04-2025", "31-03-2026", company=name))
    assert root.find(".//SVCurrentCompany").text == name
    assert root.find(".//SVFROMDATE").text == "01-04-2025"
    assert root.find(".//SVTODATE").text == "31-03-2026"


def test_no_company_means_no_company_variable():
    assert ET.fromstring(wrap_collection("C1", "Ledger", ["Name"])).find(".//SVCurrentCompany") is None
    assert ET.fromstring(wrap_report("Trial Balance", "01-04-2025", "31-03-2026")).find(".//SVCurrentCompany") is None


def test_collection_filters_round_trip():
    xml = wrap_collection(
        "C2", "Voucher", ["GUID", "AlterID"],
        static_vars={"SVFROMDATE": "01-06-2023", "SVTODATE": "30-06-2023"},
        filters=[("S0Alt", "$AlterID > 5"), ("S0Date", '$Date < $$Date:"01-07-2023"')],
    )
    root = ET.fromstring(xml)
    assert [f.text for f in root.iter("FILTER")] == ["S0Alt", "S0Date"]
    systems = {s.get("NAME"): s.text for s in root.iter("SYSTEM")}
    assert systems == {"S0Alt": "$AlterID > 5", "S0Date": '$Date < $$Date:"01-07-2023"'}
    assert [m.text for m in root.iter("NATIVEMETHOD")] == ["GUID", "AlterID"]
    assert root.find(".//SVFROMDATE").text == "01-06-2023"


def test_invalid_static_variable_name_rejected():
    with pytest.raises(ValueError):
        wrap_collection("C3", "Ledger", ["Name"], static_vars={"SV DATE": "x"})


def test_build_company_list_shape():
    root = ET.fromstring(build_company_list())
    assert root.find(".//ID").text == "List of Companies"
    assert root.find(".//COLLECTION/TYPE").text == "Company"
    assert [m.text for m in root.iter("NATIVEMETHOD")] == ["Name"]


def test_esc_and_formula_string():
    assert esc("A & B's \"x\" <y>") == "A &amp; B&apos;s &quot;x&quot; &lt;y&gt;"
    assert formula_string("Bank Charges") == '"Bank Charges"'
    with pytest.raises(ValueError):
        formula_string('say "hi"')
```

`v2/tests/agent/test_client.py`:
```python
import httpx
import pytest

from v2.agent.tally import client as client_module
from v2.agent.tally.client import TallyClient
from v2.agent.tally.exceptions import TallyConnectionError, TallyResponseError, TallyTimeoutError


def _client(handler):
    return TallyClient(transport=httpx.MockTransport(handler))


async def test_post_returns_text_raw_bytes_and_elapsed():
    c = _client(lambda request: httpx.Response(200, content="<E>शर्मा&#4;</E>".encode("utf-8")))
    response = await c.post_xml("<ENVELOPE/>")
    assert response.text == "<E>शर्मा&#4;</E>"
    assert response.raw == "<E>शर्मा&#4;</E>".encode("utf-8")
    assert response.response_bytes == len(response.raw)
    assert response.elapsed_ms >= 0


async def test_request_body_is_utf8():
    seen = {}

    def handler(request):
        seen["body"] = request.content
        return httpx.Response(200, content=b"<E/>")

    await _client(handler).post_xml("<X>शर्मा ट्रेडर्स</X>")
    assert "शर्मा ट्रेडर्स".encode("utf-8") in seen["body"]


async def test_timeout_raises_timeout_error():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(TallyTimeoutError):
        await _client(handler).post_xml("<X/>")


async def test_refused_raises_connection_error_not_timeout():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(TallyConnectionError) as info:
        await _client(handler).post_xml("<X/>")
    assert not isinstance(info.value, TallyTimeoutError)


async def test_http_error_raises_response_error():
    with pytest.raises(TallyResponseError):
        await _client(lambda request: httpx.Response(500)).post_xml("<X/>")


async def test_timeout_is_clamped_to_max():
    seen = {}

    def handler(request):
        seen["timeout"] = request.extensions["timeout"]
        return httpx.Response(200, content=b"<E/>")

    await _client(handler).post_xml("<X/>", timeout=500)
    assert seen["timeout"]["read"] == client_module.MAX_TIMEOUT_S
    assert seen["timeout"]["connect"] == client_module.CONNECT_TIMEOUT_S


async def test_default_timeout():
    seen = {}

    def handler(request):
        seen["timeout"] = request.extensions["timeout"]
        return httpx.Response(200, content=b"<E/>")

    await _client(handler).post_xml("<X/>")
    assert seen["timeout"]["read"] == client_module.DEFAULT_TIMEOUT_S


async def test_health_check():
    ok = _client(lambda request: httpx.Response(200, content=b"<ENVELOPE><COMPANY NAME='x'/></ENVELOPE>"))
    assert await ok.health_check() is True

    def down(request):
        raise httpx.ConnectError("refused", request=request)

    assert await _client(down).health_check() is False


def test_no_mock_mode_in_v2_client():
    assert not hasattr(TallyClient(), "mock_mode")
    assert "mock_handler" not in open(client_module.__file__, encoding="utf-8").read()
```

`v2/tests/test_copied_headers.py`:
```python
"""Every copied file names its source and commit on line 1 (Part 1 §5 "Code isolation (v2)")."""
import re
from pathlib import Path

import pytest

V2_ROOT = Path(__file__).resolve().parents[1]
HEADER = re.compile(r"^# Copied from: (?P<src>\S+) @ (?P<commit>[0-9a-f]{7,40})$")
COPIED = {
    "agent/tally/exceptions.py": "backend/tally_bridge/exceptions.py",
    "agent/tally/xml_utils.py": "backend/tally_bridge/response_parser.py",
    "agent/tally/envelopes.py": "backend/tally_bridge/request_builder.py",
    "agent/tally/client.py": "backend/tally_bridge/client.py",
}


@pytest.mark.parametrize("rel,source", sorted(COPIED.items()))
def test_copied_file_header(rel, source):
    lines = (V2_ROOT / rel).read_text(encoding="utf-8").splitlines()
    match = HEADER.match(lines[0])
    assert match, f"{rel} line 1 must be '# Copied from: <path> @ <commit>'"
    assert match["src"] == source
    assert lines[1].startswith("# Changes:")
```

- [x] **Step 3: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.agent.tally.xml_utils'` (and the other new modules).

- [x] **Step 4: Write `v2/agent/tally/exceptions.py`**

```python
# Copied from: backend/tally_bridge/exceptions.py @ c04d7d2
# Changes: added TallyTimeoutError so a timeout is told apart from a refused connection.
"""Exceptions raised by the v2 Tally read client."""


class TallyConnectionError(Exception):
    """Raised when TallyPrime is unreachable."""


class TallyTimeoutError(TallyConnectionError):
    """Raised when TallyPrime accepted the connection but did not answer in time."""


class TallyResponseError(Exception):
    """Raised when TallyPrime returns an HTTP error or an unparseable response."""
```

- [x] **Step 5: Write `v2/agent/tally/xml_utils.py`**

```python
# Copied from: backend/tally_bridge/response_parser.py @ c04d7d2
# Changes: sanitize_xml, detect_error and _get_text (now get_text) as-is; parse_company_list only counts COMPANY
# elements with a NAME child or attribute (the source also counts CMPINFO's <COMPANY>0</COMPANY> as a company);
# added read_objects.
"""XML helpers for Tally responses."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET


def sanitize_xml(raw_xml: str) -> str:
    """Remove invalid XML character references that TallyPrime sometimes emits (e.g. &#4;)."""
    return re.sub(r"&#([0-8]|1[0-1]|1[4-9]|2[0-9]|3[0-1]);", "", raw_xml)


def detect_error(raw_xml: str) -> str | None:
    try:
        root = ET.fromstring(sanitize_xml(raw_xml))
    except ET.ParseError:
        return "Invalid XML response from Tally"
    error_el = root.find(".//LINEERROR")
    if error_el is not None and error_el.text:
        return error_el.text.strip()
    errors_el = root.find(".//ERRORS")
    if errors_el is not None and errors_el.text and errors_el.text.strip() != "0":
        return f"Tally reported {errors_el.text.strip()} error(s)"
    return None


def get_text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def parse_company_list(raw_xml: str) -> list[str]:
    """Names of the companies in a company-list response. CMPINFO's bare count elements are ignored."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    names: list[str] = []
    for comp in root.iter("COMPANY"):
        name = (get_text(comp, "NAME") or comp.get("NAME", "")).strip()
        if name:
            names.append(name)
    return names


def read_objects(raw_xml: str, tag: str, fields: list[str]) -> list[dict[str, str]]:
    """Read `fields` (Tally method names, any case) from every `tag` element; a missing field is "".

    Elements with neither children nor attributes (e.g. CMPINFO's <COMPANY>0</COMPANY>) are skipped.
    NAME falls back to the element's NAME attribute.
    """
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows: list[dict[str, str]] = []
    for element in root.iter(tag.upper()):
        if len(element) == 0 and not element.attrib:
            continue
        row: dict[str, str] = {}
        for field in fields:
            value = get_text(element, field.upper())
            if not value and field.upper() == "NAME":
                value = element.get("NAME", "").strip()
            row[field] = value
        rows.append(row)
    return rows
```

- [x] **Step 6: Write `v2/agent/tally/envelopes.py`**

```python
# Copied from: backend/tally_bridge/request_builder.py @ c04d7d2
# Changes: the company name is always XML-escaped (the source leaves it raw in _wrap_voucher_collection,
# _wrap_report_envelope and build_ledger_vouchers — Part 1 R13); the collection wrapper also takes static
# variables, filters and extra TDL; only the wrappers and build_company_list are copied.
"""Pure XML envelope builders for Tally export requests. No I/O."""
from __future__ import annotations

import re
from xml.sax.saxutils import escape as _xml_escape

COMPANY_PLACEHOLDER = "__COMPANY__"
_VAR_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


def esc(value: str) -> str:
    """Escape text for XML element content or attribute values."""
    return _xml_escape(value, {'"': "&quot;", "'": "&apos;"})


def formula_string(value: str) -> str:
    """A TDL string literal for formulas like `$Name = "..."`. Values containing '"' are refused."""
    if '"' in value:
        raise ValueError(f"Can't put a double quote inside a TDL string literal: {value!r}")
    return f'"{value}"'


def _static_vars(company: str | None, static_vars: dict[str, str] | None) -> str:
    lines = ["<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>"]
    for name, value in (static_vars or {}).items():
        if not _VAR_NAME.match(name):
            raise ValueError(f"Invalid static variable name: {name!r}")
        lines.append(f"<{name}>{esc(value)}</{name}>")
    if company:
        lines.append(f"<SVCurrentCompany>{esc(company)}</SVCurrentCompany>")
    return "\n".join(lines)


def wrap_collection(
    collection_name: str,
    object_type: str,
    native_methods: list[str],
    company: str | None = None,
    *,
    static_vars: dict[str, str] | None = None,
    filters: list[tuple[str, str]] | None = None,
    extra_collection_xml: str = "",
    extra_tdl_xml: str = "",
) -> str:
    """A TDL collection export. `filters` are (name, formula) pairs; formulas are XML-escaped."""
    filters = filters or []
    filter_refs = "\n".join(f"<FILTER>{esc(name)}</FILTER>" for name, _ in filters)
    methods_xml = "\n".join(f"<NATIVEMETHOD>{method}</NATIVEMETHOD>" for method in native_methods)
    systems = "\n".join(
        f'<SYSTEM TYPE="Formulae" NAME="{esc(name)}">{_xml_escape(formula)}</SYSTEM>' for name, formula in filters
    )
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>{esc(collection_name)}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
{_static_vars(company, static_vars)}
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="{esc(collection_name)}" ISMODIFY="No">
<TYPE>{esc(object_type)}</TYPE>
{filter_refs}
{methods_xml}
{extra_collection_xml}
</COLLECTION>
{systems}
{extra_tdl_xml}
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""


def wrap_report(
    report_id: str,
    from_date: str,
    to_date: str,
    company: str | None = None,
    extra_vars: dict[str, str] | None = None,
) -> str:
    """A TYPE=Data report export (Trial Balance, Bills Receivable, …). Dates are DD-MM-YYYY."""
    variables = {"SVFROMDATE": from_date, "SVTODATE": to_date, **(extra_vars or {})}
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>{esc(report_id)}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
{_static_vars(company, variables)}
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""


def build_company_list() -> str:
    """List loaded companies (verified live as probe E7 — Collection TYPE=Company)."""
    return wrap_collection("List of Companies", "Company", ["Name"])
```

- [x] **Step 7: Write `v2/agent/tally/client.py`**

```python
# Copied from: backend/tally_bridge/client.py @ c04d7d2
# Changes: no mock mode (the mock handler module is never copied into v2/agent); per-request timeout (default 30 s, max 90 s);
# post_xml returns a TallyResponse with elapsed ms and the raw bytes; timeouts raise TallyTimeoutError;
# optional httpx transport for tests.
"""Async HTTP client for TallyPrime's XML server (read requests only)."""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from v2.agent.tally.envelopes import build_company_list
from v2.agent.tally.exceptions import TallyConnectionError, TallyResponseError, TallyTimeoutError

DEFAULT_TIMEOUT_S = 30.0
MAX_TIMEOUT_S = 90.0
CONNECT_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class TallyResponse:
    text: str
    raw: bytes
    elapsed_ms: int

    @property
    def response_bytes(self) -> int:
        return len(self.raw)


class TallyClient:
    def __init__(self, host: str = "localhost", port: int = 9000, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = f"http://{host}:{port}"
        self._client = httpx.AsyncClient(transport=transport)

    async def post_xml(self, xml_payload: str, timeout: float | None = None) -> TallyResponse:
        seconds = min(timeout or DEFAULT_TIMEOUT_S, MAX_TIMEOUT_S)
        started = time.perf_counter()
        try:
            response = await self._client.post(
                self.base_url,
                content=xml_payload.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
                timeout=httpx.Timeout(seconds, connect=CONNECT_TIMEOUT_S),
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TallyTimeoutError(f"TallyPrime at {self.base_url} did not answer within {seconds:.0f}s") from exc
        except httpx.ConnectError as exc:
            raise TallyConnectionError(f"Cannot connect to TallyPrime at {self.base_url}") from exc
        except httpx.HTTPStatusError as exc:
            raise TallyResponseError(f"Tally returned HTTP {exc.response.status_code}") from exc
        except httpx.TransportError as exc:
            raise TallyConnectionError(f"Transport error talking to TallyPrime at {self.base_url}: {exc}") from exc
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return TallyResponse(text=response.text, raw=response.content, elapsed_ms=elapsed_ms)

    async def close(self) -> None:
        await self._client.aclose()

    async def health_check(self) -> bool:
        try:
            result = await self.post_xml(build_company_list())
        except (TallyConnectionError, TallyResponseError):
            return False
        return "COMPANY" in result.text.upper()
```

- [x] **Step 8: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass (isolation 2 + xml_utils 5 + envelopes 15 + client 9 + headers 4).

- [x] **Step 9: Tracker** — §3 row "`v2/` scaffold" → ✅ with proof `v2/tests` all passed (Tasks 1–2).

---

### Task 3: Decimal amounts + report parsers

**Files:**
- Create: `v2/agent/tally/amounts.py`, `v2/agent/tally/reports.py`
- Modify: `v2/tests/test_copied_headers.py` (add `reports.py` to `COPIED`)
- Test: `v2/tests/agent/test_amounts.py`, `v2/tests/agent/test_reports.py`

**Interfaces:**
- Consumes: `xml_utils.get_text`, `xml_utils.sanitize_xml`
- Produces:
  - `amounts`: `AmountParseError(ValueError)` with `.raw`, `parse_decimal(text: str | None) -> Decimal | None`
  - `reports`: `parse_trial_balance(str) -> list[dict]` (keys `account_name`, `debit_amount`, `credit_amount`,
    `closing_balance`), `parse_ledger_list(str) -> list[dict]` (`name`, `parent_group`, `closing_balance`,
    `opening_balance`), `parse_bills(str) -> list[dict]` (`bill_number`, `party_name`, `bill_date`, `amount`,
    `pending_amount`, `due_date`, `overdue_days`), `parse_stock_summary(str) -> list[dict]` (`name`, `base_units`,
    `closing_quantity`, `closing_rate`, `closing_value`). All amounts `Decimal | None`.

- [x] **Step 1: Write the failing tests**

`v2/tests/agent/test_amounts.py`:
```python
from decimal import Decimal

import pytest

from v2.agent.tally.amounts import AmountParseError, parse_decimal


@pytest.mark.parametrize("text,expected", [
    ("-1048846.53", Decimal("-1048846.53")),
    ("0", Decimal("0")),
    ("1,23,456.00", Decimal("123456.00")),
    ("  55856.21 ", Decimal("55856.21")),
])
def test_plain_numbers(text, expected):
    value = parse_decimal(text)
    assert value == expected
    assert isinstance(value, Decimal)


@pytest.mark.parametrize("text", [None, "", "   "])
def test_missing_is_none_not_zero(text):
    assert parse_decimal(text) is None


def test_forex_expression_raises_with_raw_text():
    raw = "-$1,000.00 @ ₹83.00/$ = -₹83,000.00"
    with pytest.raises(AmountParseError) as info:
        parse_decimal(raw)
    assert info.value.raw == raw
```

`v2/tests/agent/test_reports.py`:
```python
from decimal import Decimal
from pathlib import Path

from v2.agent.tally.reports import parse_bills, parse_ledger_list, parse_stock_summary, parse_trial_balance

SAMPLES = Path(__file__).resolve().parents[1] / "fixtures" / "tally_samples"


def _read(name):
    return (SAMPLES / name).read_text(encoding="utf-8")


def test_trial_balance_live():
    rows = parse_trial_balance(_read("trial_balance_live.xml"))
    assert [r["account_name"] for r in rows] == [
        "Capital Account", "Current Liabilities", "Fixed Assets", "Current Assets",
        "Sales Accounts", "Purchase Accounts", "Indirect Expenses",
    ]
    capital, liabilities = rows[0], rows[1]
    assert capital["debit_amount"] is None
    assert capital["credit_amount"] == Decimal("100000.00")
    assert capital["closing_balance"] == Decimal("100000.00")
    assert liabilities["closing_balance"] == Decimal("-223528.66")
    assert rows[3]["debit_amount"] == Decimal("-1048846.53")  # debit is negative
    assert sum(r["closing_balance"] for r in rows) == Decimal("0.00")
    assert all(isinstance(r["closing_balance"], Decimal) for r in rows)


def test_ledger_list_missing_opening_is_none():
    ledgers = parse_ledger_list(_read("ledger_list.xml"))
    assert len(ledgers) == 34
    assert ledgers[0] == {
        "name": "Apex Technologies Pvt Ltd",
        "parent_group": "North Zone Debtors",
        "closing_balance": Decimal("-55000.00"),
        "opening_balance": None,
    }
    assert any(l["name"] == "Sharma & Sons Traders" for l in ledgers)


def test_bills_receivable_live():
    bills = parse_bills(_read("bills_receivable_live.xml"))
    assert len(bills) == 12
    assert bills[0]["bill_number"] == "#1"
    assert bills[0]["party_name"] == "HCODE TECHNOLOGIES PRIVATE LIMITED"
    assert bills[0]["amount"] == Decimal("200000.00")
    assert bills[0]["overdue_days"] == 272
    assert sum(b["amount"] for b in bills) == Decimal("2360000.00")


def test_bills_payable_live():
    bills = parse_bills(_read("bills_payable_live.xml"))
    assert [(b["bill_number"], b["party_name"], b["amount"]) for b in bills] == [
        ("6ZBO7JXW-0003", "Anthropic, PBC", Decimal("2096.86")),
    ]


def test_stock_summary_live():
    items = parse_stock_summary(_read("stock_summary_live.xml"))
    assert len(items) == 5
    first = items[0]
    assert first["name"] == "Data Cleaning and Matching Application Software"
    assert first["closing_quantity"] == Decimal("-1.0000")
    assert first["base_units"] == "NOS"
    assert first["closing_rate"] is None
    assert first["closing_value"] is None


def test_stock_rate_with_unit_suffix():
    xml = (
        "<ENVELOPE><DSPACCNAME><DSPDISPNAME>Box</DSPDISPNAME></DSPACCNAME><DSPSTKINFO><DSPSTKCL>"
        "<DSPCLQTY>1,200.0000 Box of 10 Nos</DSPCLQTY><DSPCLRATE>1,250.00/Box</DSPCLRATE>"
        "<DSPCLAMTA>-1500000.00</DSPCLAMTA></DSPSTKCL></DSPSTKINFO></ENVELOPE>"
    )
    item = parse_stock_summary(xml)[0]
    assert item["closing_quantity"] == Decimal("1200.0000")
    assert item["base_units"] == "Box of 10 Nos"
    assert item["closing_rate"] == Decimal("1250.00")
    assert item["closing_value"] == Decimal("-1500000.00")
```

In `v2/tests/test_copied_headers.py`, add to `COPIED`:
```python
    "agent/tally/reports.py": "backend/tally_bridge/response_parser.py",
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/agent/test_amounts.py v2/tests/agent/test_reports.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.agent.tally.amounts'`.

- [x] **Step 3: Write `v2/agent/tally/amounts.py`**

```python
"""Decimal amounts for Tally values: never float, and a missing value is never silently zero.

New in v2 (Part 1 §13): the current parse_amount returns 0.0 for anything it can't parse, which turns a parse
failure into a legitimate-looking zero (a false parity match).
"""
from __future__ import annotations

import re
from decimal import Decimal

_PLAIN_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


class AmountParseError(ValueError):
    """The text is present but is not a plain number (e.g. a forex expression)."""

    def __init__(self, raw: str):
        super().__init__(f"Not a plain Tally amount: {raw!r}")
        self.raw = raw


def parse_decimal(text: str | None) -> Decimal | None:
    """'-1,048,846.53' → Decimal('-1048846.53'); '' or None → None; anything else raises AmountParseError."""
    if text is None or not text.strip():
        return None
    cleaned = text.strip().replace(",", "")
    if not _PLAIN_NUMBER.match(cleaned):
        raise AmountParseError(text)
    return Decimal(cleaned)
```

- [x] **Step 4: Write `v2/agent/tally/reports.py`**

```python
# Copied from: backend/tally_bridge/response_parser.py @ c04d7d2
# Changes: parse_trial_balance, parse_ledger_list, parse_bills and parse_stock_summary return Decimal (via
# amounts.parse_decimal) and None for a missing value instead of float 0.0; a stock rate like "1250.00/NOS" is
# read as its number (the source's parse_amount turned it into 0.0).
"""Parsers for Tally report and ledger-list responses (Decimal amounts)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from v2.agent.tally.amounts import parse_decimal
from v2.agent.tally.xml_utils import get_text, sanitize_xml


def _sum_optional(*values: Decimal | None) -> Decimal | None:
    present = [v for v in values if v is not None]
    return sum(present, Decimal("0")) if present else None


def _parse_overdue_days(text: str) -> int | None:
    """Overdue days from Tally — handles '45', '-10', '45 Days'."""
    if not text or not text.strip():
        return None
    try:
        return int(text.strip().split()[0])
    except ValueError:
        return None


def parse_trial_balance(raw_xml: str) -> list[dict]:
    """TB rows from TYPE=Data: DSPACCNAME/DSPDISPNAME followed by DSPACCINFO (DSPCLDRAMTA debit, DSPCLCRAMTA credit)."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows: list[dict] = []
    current_name = None
    for child in list(root):
        if child.tag == "DSPACCNAME":
            current_name = get_text(child, "DSPDISPNAME")
        elif child.tag == "DSPACCINFO" and current_name:
            debit_el = child.find("DSPCLDRAMT")
            credit_el = child.find("DSPCLCRAMT")
            debit = parse_decimal(get_text(debit_el, "DSPCLDRAMTA")) if debit_el is not None else None
            credit = parse_decimal(get_text(credit_el, "DSPCLCRAMTA")) if credit_el is not None else None
            rows.append({
                "account_name": current_name,
                "debit_amount": debit,
                "credit_amount": credit,
                "closing_balance": _sum_optional(debit, credit),
            })
            current_name = None
    return rows


def parse_ledger_list(raw_xml: str) -> list[dict]:
    root = ET.fromstring(sanitize_xml(raw_xml))
    ledgers: list[dict] = []
    for ledger in root.iter("LEDGER"):
        name = get_text(ledger, "NAME") or ledger.get("NAME", "")
        if not name:
            continue
        ledgers.append({
            "name": name,
            "parent_group": get_text(ledger, "PARENT"),
            "closing_balance": parse_decimal(get_text(ledger, "CLOSINGBALANCE")),
            "opening_balance": parse_decimal(get_text(ledger, "OPENINGBALANCE")),
        })
    return ledgers


def parse_bills(raw_xml: str) -> list[dict]:
    """Bills Receivable/Payable: BILLFIXED (ref, party, date) followed by sibling BILLCL/BILLDUE/BILLOVERDUE."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    bills: list[dict] = []
    elements = list(root.iter())
    for i, el in enumerate(elements):
        if el.tag != "BILLFIXED":
            continue
        bill_ref = get_text(el, "BILLREF")
        if not bill_ref:
            continue
        amount: Decimal | None = None
        due_date = ""
        overdue = ""
        for sib in elements[i + 1: i + 10]:
            if sib.tag == "BILLFIXED":
                break
            if sib.tag == "BILLCL" and sib.text:
                parsed = parse_decimal(sib.text)
                amount = abs(parsed) if parsed is not None else None
            elif sib.tag == "BILLDUE" and sib.text:
                due_date = sib.text.strip()
            elif sib.tag == "BILLOVERDUE" and sib.text:
                overdue = sib.text.strip()
        bills.append({
            "bill_number": bill_ref,
            "party_name": get_text(el, "BILLPARTY"),
            "bill_date": get_text(el, "BILLDATE"),
            "amount": amount,
            "pending_amount": amount,
            "due_date": due_date,
            "overdue_days": _parse_overdue_days(overdue),
        })
    return bills


def _number_before(text: str, separator: str) -> Decimal | None:
    """'1,250.00/NOS' → Decimal('1250.00') with separator '/'."""
    if not text.strip():
        return None
    return parse_decimal(text.split(separator)[0])


def parse_stock_summary(raw_xml: str) -> list[dict]:
    """Stock Summary: DSPACCNAME/DSPDISPNAME followed by DSPSTKINFO/DSPSTKCL (DSPCLQTY '-2.0000 NOS', DSPCLRATE, DSPCLAMTA)."""
    root = ET.fromstring(sanitize_xml(raw_xml))
    items: list[dict] = []
    current_name = None
    for child in list(root):
        if child.tag == "DSPACCNAME":
            current_name = get_text(child, "DSPDISPNAME")
        elif child.tag == "DSPSTKINFO" and current_name:
            stk_cl = child.find("DSPSTKCL")
            qty: Decimal | None = None
            unit = ""
            rate: Decimal | None = None
            value: Decimal | None = None
            if stk_cl is not None:
                qty_parts = get_text(stk_cl, "DSPCLQTY").split()
                if qty_parts:
                    qty = parse_decimal(qty_parts[0])
                    unit = " ".join(qty_parts[1:])
                rate = _number_before(get_text(stk_cl, "DSPCLRATE"), "/")
                value = parse_decimal(get_text(stk_cl, "DSPCLAMTA"))
            items.append({
                "name": current_name,
                "base_units": unit,
                "closing_quantity": qty,
                "closing_rate": rate,
                "closing_value": value,
            })
            current_name = None
    return items
```

- [x] **Step 5: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass.

---

### Task 4: Harness core — outcomes, guards, capture, results store

**Files:**
- Create: `v2/probes/core.py`, `v2/probes/safety.py`, `v2/probes/capture.py`, `v2/probes/results.py`
- Test: `v2/tests/probes/test_core.py`, `v2/tests/probes/test_safety.py`, `v2/tests/probes/test_capture.py`,
  `v2/tests/probes/test_results.py`

**Interfaces:**
- Consumes: `client.TallyResponse`
- Produces:
  - `core`: `Outcome` (`CONFIRMED`, `DIFFERENT`, `FAILED`, `BLOCKED`, `PARTIAL`), `ProbeBlocked(Exception)`,
    `PartResult(outcome, summary, observations={}, spec_impact="")`, `PartFn`,
    `Probe(id, name, question, feeds: tuple[str, ...], parts: dict[str, PartFn], requires=(), mutating=False, guard=True)`,
    `combine(dict[str, Outcome | None]) -> Outcome`
  - `safety`: `GuardError(Exception)`, `check_request(xml: str) -> None`, `check_company(loaded: list[str], expected: str, *, mutating: bool) -> None`
  - `capture`: `TIMING_NOTE`, `fixture_name(probe_id, part, step) -> str`, `Capture(fixtures_dir)` with
    `save(*, probe_id, part, step, company_name, company_guid, request_xml, sent_at, environment, response=None, error=None) -> str`
  - `results`: `ResultsStore(path)` with `.data`, `.environment`, `save()`, `update_environment(**values)`,
    `confirmed(name) -> dict | None`, `confirm_request(name, probe_id, xml_template, **extra)`,
    `probe_entry(probe_id) -> dict | None`, `outcome(probe_id) -> Outcome | None`,
    `record_part(probe_id, part, result, *, all_parts, fixtures, manual_steps, ran_at) -> Outcome`

- [x] **Step 1: Write the failing tests**

`v2/tests/probes/test_core.py`:
```python
import pytest

from v2.probes.core import Outcome, PartResult, combine

C, D, F, B = Outcome.CONFIRMED, Outcome.DIFFERENT, Outcome.FAILED, Outcome.BLOCKED


@pytest.mark.parametrize("parts,expected", [
    ({"A": C}, C),
    ({"A": C, "B": C}, C),
    ({"A": C, "B": D}, D),
    ({"A": C, "B": F}, F),
    ({"A": F, "B": D}, F),
    ({"A": B, "B": F}, B),
    ({"A": F, "B": None}, Outcome.PARTIAL),
    ({"A": C, "B": None}, Outcome.PARTIAL),
    ({}, Outcome.PARTIAL),
])
def test_combine_precedence(parts, expected):
    assert combine(parts) is expected


def test_different_and_failed_need_spec_impact():
    with pytest.raises(ValueError):
        PartResult(D, "x")
    with pytest.raises(ValueError):
        PartResult(F, "x", spec_impact="  ")
    assert PartResult(F, "x", spec_impact="fallback").spec_impact == "fallback"
    assert PartResult(C, "ok").spec_impact == ""
    assert PartResult(B, "timeout").outcome is B


def test_partial_is_never_a_part_outcome():
    with pytest.raises(ValueError):
        PartResult(Outcome.PARTIAL, "x")
```

`v2/tests/probes/test_safety.py`:
```python
import pytest

from v2.probes.safety import GuardError, check_company, check_request

A = "Bharat Traders Probe Copy"


@pytest.mark.parametrize("xml", [
    "<COLLECTION><NATIVEMETHOD>*</NATIVEMETHOD></COLLECTION>",
    "<NATIVEMETHOD> AllLedgerEntries.* </NATIVEMETHOD>",
    "<FETCHLIST><FETCH>*</FETCH></FETCHLIST>",
    "<SYSTEM>$$InDateRange:$Date:$$Date:1:$$Date:2</SYSTEM>",
    "<system>$$indaterange</system>",
])
def test_forbidden_requests_refused(xml):
    with pytest.raises(GuardError):
        check_request(xml)


def test_clean_request_allowed():
    check_request("<NATIVEMETHOD>GUID</NATIVEMETHOD><SYSTEM>$AlterID > 5</SYSTEM>")


def test_company_guard_cases():
    check_company([A], A, mutating=False)
    check_company([A], A, mutating=True)
    with pytest.raises(GuardError, match="No company open"):
        check_company([], A, mutating=False)
    with pytest.raises(GuardError, match="2 companies are loaded"):
        check_company([A, "Other"], A, mutating=False)
    with pytest.raises(GuardError, match="expects"):
        check_company(["Bharat Traders Private Limited"], A, mutating=False)


def test_mutation_guard_needs_probe_in_name():
    with pytest.raises(GuardError, match="only companies with 'Probe'"):
        check_company(["Bharat Traders Private Limited"], "Bharat Traders Private Limited", mutating=True)
```

`v2/tests/probes/test_capture.py`:
```python
import json
from datetime import datetime, timezone

import pytest

from v2.agent.tally.client import TallyResponse
from v2.probes.capture import TIMING_NOTE, Capture, fixture_name

SENT = datetime(2026, 9, 23, 10, 12, 3, tzinfo=timezone.utc)


def _save(capture, **overrides):
    kwargs = dict(probe_id=16, part="A", step="ledgers_asof_2025-10-31", company_name="Bharat Traders Probe Copy",
                  company_guid="g-1", request_xml="<ENVELOPE/>", sent_at=SENT,
                  environment={"licence": "licensed"})
    kwargs.update(overrides)
    return capture.save(**kwargs)


def test_fixture_name():
    assert fixture_name(1, "A", "counters_baseline") == "p01_A_counters_baseline.xml"
    with pytest.raises(ValueError):
        fixture_name(1, "A", "Bad Step")


def test_saves_raw_bytes_exactly_and_sidecar(tmp_path):
    raw = "<E>शर्मा&#4;</E>".encode("utf-8")
    name = _save(Capture(tmp_path), response=TallyResponse(text=raw.decode(), raw=raw, elapsed_ms=412))

    assert name == "p16_A_ledgers_asof_2025-10-31.xml"
    assert (tmp_path / name).read_bytes() == raw
    sidecar = json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
    assert sidecar == {
        "probe": 16, "part": "A", "step": "ledgers_asof_2025-10-31",
        "company_name": "Bharat Traders Probe Copy", "company_guid": "g-1",
        "sent_at": "2026-09-23T10:12:03+00:00", "elapsed_ms": 412, "response_bytes": len(raw),
        "timing_note": TIMING_NOTE, "request_xml": "<ENVELOPE/>", "environment": {"licence": "licensed"},
    }


def test_error_writes_sidecar_only(tmp_path):
    name = _save(Capture(tmp_path), step="popup_read", error={"kind": "timeout", "message": "no answer"})
    assert not (tmp_path / name).exists()
    sidecar = json.loads((tmp_path / f"{name}.json").read_text(encoding="utf-8"))
    assert sidecar["error"] == {"kind": "timeout", "message": "no answer"}
    assert sidecar["elapsed_ms"] is None
```

`v2/tests/probes/test_results.py`:
```python
import json
from datetime import datetime, timezone
from decimal import Decimal

from v2.probes.core import Outcome, PartResult
from v2.probes.results import ResultsStore

T1 = datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 9, 23, 11, 0, tzinfo=timezone.utc)


def _record(store, part, result, ran_at=T1, all_parts=("A", "B")):
    return store.record_part(16, part, result, all_parts=list(all_parts), fixtures=["p16_A_x.xml"],
                             manual_steps=[], ran_at=ran_at)


def test_partial_then_combined(tmp_path):
    store = ResultsStore(tmp_path / "results.json")
    assert _record(store, "A", PartResult(Outcome.CONFIRMED, "ok")) is Outcome.PARTIAL
    assert _record(store, "B", PartResult(Outcome.DIFFERENT, "diff", spec_impact="change")) is Outcome.DIFFERENT
    assert store.outcome(16) is Outcome.DIFFERENT
    reloaded = ResultsStore(tmp_path / "results.json")
    assert reloaded.probe_entry(16)["parts"]["B"]["spec_impact"] == "change"


def test_rerun_moves_previous_into_history(tmp_path):
    store = ResultsStore(tmp_path / "results.json")
    _record(store, "A", PartResult(Outcome.BLOCKED, "timeout"), all_parts=("A",))
    _record(store, "A", PartResult(Outcome.CONFIRMED, "ok"), ran_at=T2, all_parts=("A",))
    entry = store.probe_entry(16)
    assert entry["outcome"] == "CONFIRMED"
    assert [h["outcome"] for h in entry["history"]] == ["BLOCKED"]
    assert entry["history"][0]["part"] == "A"


def test_confirmed_requests_and_environment(tmp_path):
    store = ResultsStore(tmp_path / "results.json")
    assert store.confirmed("company_counters") is None
    store.confirm_request("company_counters", 1, "<X/>", fields=["GUID"])
    store.update_environment(licence="licensed")
    data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert data["confirmed_requests"]["company_counters"] == {"probe": 1, "xml_template": "<X/>", "fields": ["GUID"]}
    assert data["environment"] == {"licence": "licensed"}


def test_decimal_observations_serialise(tmp_path):
    store = ResultsStore(tmp_path / "results.json")
    _record(store, "A", PartResult(Outcome.CONFIRMED, "ok", observations={"total": Decimal("970537.00")}), all_parts=("A",))
    data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert data["probes"]["16"]["parts"]["A"]["observations"]["total"] == "970537.00"
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.core'`.

- [x] **Step 3: Write `v2/probes/core.py`**

```python
"""Probe types: outcomes, part results, the Probe record, and how part outcomes combine (S0 spec §5.1, §5.4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from v2.probes.context import ProbeContext


class Outcome(str, Enum):
    CONFIRMED = "CONFIRMED"
    DIFFERENT = "DIFFERENT"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


class ProbeBlocked(Exception):
    """A part can't continue: timeout, Tally unreachable, missing prerequisite, or a manual step in non-interactive mode."""


@dataclass
class PartResult:
    outcome: Outcome
    summary: str
    observations: dict[str, Any] = field(default_factory=dict)
    spec_impact: str = ""

    def __post_init__(self) -> None:
        if self.outcome is Outcome.PARTIAL:
            raise ValueError("PARTIAL is a probe-level outcome, never a part outcome")
        if self.outcome in (Outcome.DIFFERENT, Outcome.FAILED) and not self.spec_impact.strip():
            raise ValueError(f"{self.outcome.value} needs a spec_impact sentence")


PartFn = Callable[["ProbeContext"], Awaitable[PartResult]]


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


_PRECEDENCE = (Outcome.BLOCKED, Outcome.FAILED, Outcome.DIFFERENT)


def combine(part_outcomes: dict[str, Outcome | None]) -> Outcome:
    """Probe outcome from its parts; first match wins: PARTIAL, BLOCKED, FAILED, DIFFERENT, else CONFIRMED."""
    if not part_outcomes or any(outcome is None for outcome in part_outcomes.values()):
        return Outcome.PARTIAL
    present = set(part_outcomes.values())
    for outcome in _PRECEDENCE:
        if outcome in present:
            return outcome
    return Outcome.CONFIRMED
```

- [x] **Step 4: Write `v2/probes/safety.py`**

```python
"""Guards that run before any request is sent (S0 spec §4.5). A guard failure sends nothing."""
from __future__ import annotations

import re

_FORBIDDEN_REQUEST = (
    (re.compile(r"<NATIVEMETHOD>[^<]*\*[^<]*</NATIVEMETHOD>", re.IGNORECASE),
     "`*` as a NATIVEMETHOD crashes Tally (LESSONS §5)"),
    (re.compile(r"<FETCH>[^<]*\*[^<]*</FETCH>", re.IGNORECASE), "`*` as a FETCH value crashes Tally (LESSONS §5)"),
    (re.compile(r"\$\$InDateRange", re.IGNORECASE), "$$InDateRange crashes TallyPrime 7 (LESSONS §3)"),
)


class GuardError(Exception):
    """A guard refused; nothing was sent."""


def check_request(xml: str) -> None:
    for pattern, reason in _FORBIDDEN_REQUEST:
        if pattern.search(xml):
            raise GuardError(f"Request refused: {reason}")


def check_company(loaded: list[str], expected: str, *, mutating: bool) -> None:
    """Exactly one company loaded, and it's the expected one. Changes only on companies named '…Probe…'."""
    if not loaded:
        raise GuardError(f"No company open in Tally. Open {expected!r}.")
    if len(loaded) > 1:
        raise GuardError(f"{len(loaded)} companies are loaded ({', '.join(loaded)}). Close all but {expected!r}.")
    if loaded[0] != expected:
        raise GuardError(f"Tally has {loaded[0]!r} open, but this step expects {expected!r}.")
    if mutating and "Probe" not in expected:
        raise GuardError(f"Refusing to change {expected!r}: only companies with 'Probe' in the name may be changed.")
```

- [x] **Step 5: Write `v2/probes/capture.py`**

```python
"""Save every Tally response as a fixture plus a JSON sidecar (S0 spec §5.6)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from v2.agent.tally.client import TallyResponse

TIMING_NOTE = "Wine — not representative"
_STEP = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")


def fixture_name(probe_id: int, part: str, step: str) -> str:
    if not _STEP.match(step):
        raise ValueError(f"Step name must match {_STEP.pattern}: {step!r}")
    return f"p{probe_id:02d}_{part}_{step}.xml"


class Capture:
    def __init__(self, fixtures_dir: Path):
        self.fixtures_dir = fixtures_dir

    def save(
        self,
        *,
        probe_id: int,
        part: str,
        step: str,
        company_name: str,
        company_guid: str | None,
        request_xml: str,
        sent_at: datetime,
        environment: dict[str, Any],
        response: TallyResponse | None = None,
        error: dict[str, str] | None = None,
    ) -> str:
        """Write the raw response bytes (if any) and the sidecar; return the fixture file name."""
        name = fixture_name(probe_id, part, step)
        self.fixtures_dir.mkdir(parents=True, exist_ok=True)
        if response is not None:
            (self.fixtures_dir / name).write_bytes(response.raw)
        sidecar: dict[str, Any] = {
            "probe": probe_id,
            "part": part,
            "step": step,
            "company_name": company_name,
            "company_guid": company_guid,
            "sent_at": sent_at.isoformat(timespec="seconds"),
            "elapsed_ms": response.elapsed_ms if response else None,
            "response_bytes": response.response_bytes if response else None,
            "timing_note": TIMING_NOTE,
            "request_xml": request_xml,
            "environment": environment,
        }
        if error is not None:
            sidecar["error"] = error
        (self.fixtures_dir / f"{name}.json").write_text(
            json.dumps(sidecar, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
        )
        return name
```

- [x] **Step 6: Write `v2/probes/results.py`**

```python
"""results.json: environment, confirmed requests and per-probe results (S0 spec §5.7)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from v2.probes.core import Outcome, PartResult, combine


class ResultsStore:
    def __init__(self, path: Path):
        self.path = path
        if path.exists():
            self.data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        else:
            self.data = {"environment": {}, "confirmed_requests": {}, "probes": {}}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        tmp.replace(self.path)

    @property
    def environment(self) -> dict[str, Any]:
        return self.data["environment"]

    def update_environment(self, **values: Any) -> None:
        self.data["environment"].update(values)
        self.save()

    def confirmed(self, name: str) -> dict[str, Any] | None:
        return self.data["confirmed_requests"].get(name)

    def confirm_request(self, name: str, probe_id: int, xml_template: str, **extra: Any) -> None:
        self.data["confirmed_requests"][name] = {"probe": probe_id, "xml_template": xml_template, **extra}
        self.save()

    def probe_entry(self, probe_id: int) -> dict[str, Any] | None:
        return self.data["probes"].get(str(probe_id))

    def outcome(self, probe_id: int) -> Outcome | None:
        entry = self.probe_entry(probe_id)
        return Outcome(entry["outcome"]) if entry else None

    def record_part(
        self,
        probe_id: int,
        part: str,
        result: PartResult,
        *,
        all_parts: list[str],
        fixtures: list[str],
        manual_steps: list[dict[str, Any]],
        ran_at: datetime,
    ) -> Outcome:
        """Store one part's result (the previous run of that part moves to history); return the probe outcome."""
        entry = self.data["probes"].setdefault(
            str(probe_id), {"outcome": Outcome.PARTIAL.value, "parts": {}, "history": []}
        )
        previous = entry["parts"].get(part)
        if previous is not None:
            entry["history"].append({"part": part, **previous})
        entry["parts"][part] = {
            "outcome": result.outcome.value,
            "summary": result.summary,
            "observations": result.observations,
            "spec_impact": result.spec_impact,
            "fixtures": fixtures,
            "manual_steps": manual_steps,
            "ran_at": ran_at.isoformat(timespec="seconds"),
        }
        outcome = combine({
            label: Outcome(entry["parts"][label]["outcome"]) if label in entry["parts"] else None
            for label in all_parts
        })
        entry["outcome"] = outcome.value
        self.save()
        return outcome
```

- [x] **Step 7: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: all pass.

---

### Task 5: ProbeContext, runner, registry, report, CLI

**Files:**
- Create: `v2/probes/companies.py`, `v2/probes/console.py`, `v2/probes/context.py`, `v2/probes/runner.py`,
  `v2/probes/registry.py`, `v2/probes/report.py`, `v2/probes/__main__.py`
- Test: `v2/tests/probes/fakes.py`, `v2/tests/probes/test_runner.py`, `v2/tests/probes/test_cli.py`

**Interfaces:**
- Consumes: everything from Tasks 2–4.
- Produces:
  - `companies`: `COMPANIES = {"A": "Bharat Traders Probe Copy", "B": "Sharma & Sons' Probe Traders", "C": "Probe Vault Co"}`,
    `SEED_COMPANY = "Bharat Traders Private Limited"`, `SEED_BACKUP = "seed_data/TDBK1800_100003.001"`
  - `console`: `ProbeIO` protocol (`interactive: bool`, `wait(str)`, `ask(str) -> str`, `say(str)`), `ConsoleIO(interactive=True)`
  - `context`: `POPUP_HINT`, `select_company(text, company, fields) -> dict[str, str]`,
    `ProbeContext(*, probe, part, company_name, client, store, capture, io)` with attributes `company_name`,
    `company_guid`, `observations`, `fixtures`, `manual_steps`, `store`, and methods
    `async try_send(step, xml, timeout=None) -> tuple[str | None, dict | None]`, `async send(step, xml, timeout=None) -> str`,
    `async company_names() -> list[str]`, `async counters(step=None) -> dict[str, str]`,
    `pause(instruction)`, `ask(prompt) -> str`, `observe(key, value)`, `confirm_request(name, xml_template, **extra)`
  - `runner`: `async run_probe(probe, *, labels, client, store, capture, io) -> Outcome`,
    `async run_order(order: list[tuple[int, str]], *, client, store, capture, io) -> None`
  - `registry`: `ProbeInfo(id, name, companies, tier, deferred=False, module=None)`, `PROBES`, `FIRST_ORDER`,
    `ALL_ORDER`, `info(probe_id) -> ProbeInfo`, `load_probe(probe_id) -> Probe | None`
  - `report`: `render_report(store, generated_on: str) -> str`
  - `__main__`: `main(argv: list[str] | None = None, *, transport=None, io=None) -> int`
  - tests `fakes`: `FakeTally`, `ScriptedIO`, `company_list_xml`, `objects_xml`, `bills_xml`, `tb_xml`, `make_harness`

- [x] **Step 1: Write the test doubles** — `v2/tests/probes/fakes.py`

```python
"""Test doubles: a fake Tally XML server and a scripted console. No real Tally."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import httpx

from v2.agent.tally.client import TallyClient
from v2.agent.tally.envelopes import esc
from v2.probes.capture import Capture
from v2.probes.results import ResultsStore

Handler = Callable[[str], "str | bytes | type[Exception]"]
COMPANY_LIST_MARKER = "<ID>List of Companies</ID>"


def company_list_xml(names: list[str]) -> str:
    companies = "".join(f'<COMPANY NAME="{esc(n)}"><NAME>{esc(n)}</NAME></COMPANY>' for n in names)
    return ("<ENVELOPE><BODY><DESC><CMPINFO><COMPANY>0</COMPANY></CMPINFO></DESC>"
            f"<DATA><COLLECTION>{companies}</COLLECTION></DATA></BODY></ENVELOPE>")


def objects_xml(tag: str, rows: list[dict[str, str]]) -> str:
    body = "".join(
        f"<{tag}>" + "".join(f"<{k.upper()}>{esc(v)}</{k.upper()}>" for k, v in row.items()) + f"</{tag}>"
        for row in rows
    )
    return f"<ENVELOPE><BODY><DATA><COLLECTION>{body}</COLLECTION></DATA></BODY></ENVELOPE>"


def bills_xml(bills: list[tuple[str, str, str]]) -> str:
    """bills: (ref, party, BILLCL text)."""
    return "<ENVELOPE>" + "".join(
        f"<BILLFIXED><BILLDATE>1-Apr-25</BILLDATE><BILLREF>{esc(ref)}</BILLREF><BILLPARTY>{esc(party)}</BILLPARTY>"
        f"</BILLFIXED><BILLCL>{amount}</BILLCL><BILLDUE>1-Apr-25</BILLDUE><BILLOVERDUE>10</BILLOVERDUE>"
        for ref, party, amount in bills
    ) + "</ENVELOPE>"


def tb_xml(rows: list[tuple[str, str, str]]) -> str:
    """rows: (group, debit text, credit text)."""
    return "<ENVELOPE>" + "".join(
        f"<DSPACCNAME><DSPDISPNAME>{esc(name)}</DSPDISPNAME></DSPACCNAME><DSPACCINFO>"
        f"<DSPCLDRAMT><DSPCLDRAMTA>{debit}</DSPCLDRAMTA></DSPCLDRAMT>"
        f"<DSPCLCRAMT><DSPCLCRAMTA>{credit}</DSPCLCRAMTA></DSPCLCRAMT></DSPACCINFO>"
        for name, debit, credit in rows
    ) + "</ENVELOPE>"


class FakeTally:
    """Answers each request from the first route whose marker appears in the request XML."""

    def __init__(self, companies: list[str] | None = None):
        self.companies = list(companies or [])
        self.down = False
        self.routes: list[tuple[str, Handler]] = []
        self.requests: list[str] = []

    def route(self, marker: str, handler: Handler) -> None:
        self.routes.append((marker, handler))

    def probe_requests(self) -> list[str]:
        """Requests other than the guard's company list."""
        return [r for r in self.requests if COMPANY_LIST_MARKER not in r]

    def transport(self) -> httpx.MockTransport:
        def handle(request: httpx.Request) -> httpx.Response:
            body = request.content.decode("utf-8")
            self.requests.append(body)
            if self.down:
                raise httpx.ConnectError("connection refused", request=request)
            for marker, handler in self.routes:
                if marker in body:
                    result = handler(body)
                    if isinstance(result, type) and issubclass(result, Exception):
                        raise result("fake failure", request=request)
                    return httpx.Response(200, content=result.encode("utf-8") if isinstance(result, str) else result)
            if COMPANY_LIST_MARKER in body:
                return httpx.Response(200, content=company_list_xml(self.companies).encode("utf-8"))
            return httpx.Response(200, content=b"<ENVELOPE></ENVELOPE>")

        return httpx.MockTransport(handle)


class ScriptedIO:
    def __init__(self, answers: list[str] | None = None, interactive: bool = True,
                 on_wait: Callable[[str], None] | None = None):
        self.interactive = interactive
        self.answers = list(answers or [])
        self.on_wait = on_wait
        self.waits: list[str] = []
        self.asks: list[str] = []
        self.said: list[str] = []

    def wait(self, instruction: str) -> None:
        self.waits.append(instruction)
        if self.on_wait:
            self.on_wait(instruction)

    def ask(self, prompt: str) -> str:
        self.asks.append(prompt)
        if not self.answers:
            raise AssertionError(f"Unexpected question: {prompt}")
        return self.answers.pop(0)

    def say(self, message: str) -> None:
        self.said.append(message)


def make_harness(tmp_path: Path, fake: FakeTally) -> tuple[TallyClient, ResultsStore, Capture]:
    return (TallyClient(transport=fake.transport()),
            ResultsStore(tmp_path / "results.json"),
            Capture(tmp_path / "fixtures"))
```

- [x] **Step 2: Write the failing runner tests** — `v2/tests/probes/test_runner.py`

```python
import httpx

from v2.probes.companies import COMPANIES
from v2.probes.core import Outcome, PartResult, Probe
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import FakeTally, ScriptedIO, make_harness, objects_xml

A, B = COMPANIES["A"], COMPANIES["B"]


def _probe(parts, **kw):
    return Probe(id=99, name="fake", question="?", feeds=(), parts=parts, **kw)


async def _run(tmp_path, fake, probe, io=None, labels=None):
    client, store, capture = make_harness(tmp_path, fake)
    io = io or ScriptedIO()
    outcome = await run_probe(probe, labels=labels, client=client, store=store, capture=capture, io=io)
    return outcome, store, io


async def test_confirmed_part_records_fixture_and_observations(tmp_path):
    fake = FakeTally([A])
    fake.route("S0Thing", lambda body: "<ENVELOPE><X>1</X></ENVELOPE>")

    async def part(ctx):
        await ctx.send("thing", "<ENVELOPE><ID>S0Thing</ID></ENVELOPE>")
        ctx.observe("seen", 1)
        return PartResult(Outcome.CONFIRMED, "ok")

    outcome, store, _ = await _run(tmp_path, fake, _probe({"A": part}))
    assert outcome is Outcome.CONFIRMED
    entry = store.probe_entry(99)["parts"]["A"]
    assert entry["fixtures"] == ["p99_A_thing.xml"]
    assert entry["observations"] == {"seen": 1}
    assert (tmp_path / "fixtures" / "p99_A_thing.xml").read_text() == "<ENVELOPE><X>1</X></ENVELOPE>"


async def test_wrong_company_blocks_before_any_probe_request(tmp_path):
    fake = FakeTally(["Some Other Co"])

    async def part(ctx):
        await ctx.send("thing", "<ENVELOPE/>")
        return PartResult(Outcome.CONFIRMED, "ok")

    outcome, store, _ = await _run(tmp_path, fake, _probe({"A": part}))
    assert outcome is Outcome.BLOCKED
    assert "expects" in store.probe_entry(99)["parts"]["A"]["summary"]
    assert fake.probe_requests() == []


async def test_two_companies_loaded_blocks(tmp_path):
    outcome, store, _ = await _run(tmp_path, FakeTally([A, B]), _probe({"A": lambda ctx: None}))
    assert outcome is Outcome.BLOCKED
    assert "2 companies are loaded" in store.probe_entry(99)["parts"]["A"]["summary"]


async def test_timeout_blocks_with_popup_hint_and_error_sidecar(tmp_path):
    fake = FakeTally([A])
    fake.route("S0Slow", lambda body: httpx.ReadTimeout)

    async def part(ctx):
        await ctx.send("slow", "<ENVELOPE><ID>S0Slow</ID></ENVELOPE>")
        return PartResult(Outcome.CONFIRMED, "unreachable")

    outcome, store, _ = await _run(tmp_path, fake, _probe({"A": part}))
    entry = store.probe_entry(99)["parts"]["A"]
    assert outcome is Outcome.BLOCKED
    assert "popup" in entry["summary"]
    assert entry["fixtures"] == ["p99_A_slow.xml.json"]
    assert len([r for r in fake.probe_requests() if "S0Slow" in r]) == 1  # no retry


async def test_tally_down_blocks(tmp_path):
    fake = FakeTally([A])
    fake.down = True
    outcome, store, _ = await _run(tmp_path, fake, _probe({"A": lambda ctx: None}))
    assert outcome is Outcome.BLOCKED
    assert "not reachable" in store.probe_entry(99)["parts"]["A"]["summary"]


async def test_try_send_returns_error_instead_of_blocking(tmp_path):
    fake = FakeTally([A])
    fake.route("S0Slow", lambda body: httpx.ReadTimeout)

    async def part(ctx):
        text, error = await ctx.try_send("slow", "<ENVELOPE><ID>S0Slow</ID></ENVELOPE>")
        assert text is None and error["kind"] == "timeout"
        return PartResult(Outcome.CONFIRMED, "handled")

    outcome, _, _ = await _run(tmp_path, fake, _probe({"A": part}))
    assert outcome is Outcome.CONFIRMED


async def test_forbidden_request_refused_and_not_sent(tmp_path):
    fake = FakeTally([A])

    async def part(ctx):
        await ctx.send("bad", "<ENVELOPE><NATIVEMETHOD>*</NATIVEMETHOD></ENVELOPE>")
        return PartResult(Outcome.CONFIRMED, "unreachable")

    outcome, store, _ = await _run(tmp_path, fake, _probe({"A": part}))
    assert outcome is Outcome.BLOCKED
    assert "Request refused" in store.probe_entry(99)["parts"]["A"]["summary"]
    assert fake.probe_requests() == []


async def test_pause_non_interactive_blocks(tmp_path):
    async def part(ctx):
        ctx.pause("Delete the voucher")
        return PartResult(Outcome.CONFIRMED, "unreachable")

    outcome, store, _ = await _run(tmp_path, FakeTally([A]), _probe({"A": part}), io=ScriptedIO(interactive=False))
    assert outcome is Outcome.BLOCKED
    assert "manual step" in store.probe_entry(99)["parts"]["A"]["summary"]


async def test_pause_and_ask_are_logged(tmp_path):
    async def part(ctx):
        ctx.pause("Delete the voucher")
        ctx.observe("answer", ctx.ask("Type the balance"))
        return PartResult(Outcome.CONFIRMED, "ok")

    io = ScriptedIO(answers=["1234.00"])
    outcome, store, _ = await _run(tmp_path, FakeTally([A]), _probe({"A": part}), io=io)
    steps = store.probe_entry(99)["parts"]["A"]["manual_steps"]
    assert outcome is Outcome.CONFIRMED
    assert [s["instruction"] for s in steps] == ["Delete the voucher", "Type the balance"]
    assert steps[1]["input"] == "1234.00"


async def test_missing_prerequisite_blocks_without_requests(tmp_path):
    fake = FakeTally([A])
    outcome, store, _ = await _run(tmp_path, fake, _probe({"A": lambda ctx: None}, requires=(1,)))
    assert outcome is Outcome.BLOCKED
    assert "Run probe(s) 1 first" in store.probe_entry(99)["parts"]["A"]["summary"]
    assert fake.requests == []


async def test_counters_before_probe_1_confirmed_blocks(tmp_path):
    async def part(ctx):
        await ctx.counters("counters")
        return PartResult(Outcome.CONFIRMED, "unreachable")

    outcome, store, _ = await _run(tmp_path, FakeTally([A]), _probe({"A": part}))
    assert outcome is Outcome.BLOCKED
    assert "probe 1" in store.probe_entry(99)["parts"]["A"]["summary"]


async def test_counters_use_confirmed_template_and_fill_guid(tmp_path):
    fake = FakeTally([A])
    fake.route("S0CompanyCounters", lambda body: objects_xml("COMPANY", [{"Name": A, "GUID": "g-1", "AltVchId": "7"}]))
    client, store, capture = make_harness(tmp_path, fake)
    store.confirm_request("company_counters", 1, "<ENVELOPE><ID>S0CompanyCounters</ID></ENVELOPE>",
                          fields=["GUID", "AltVchId"])
    seen = {}

    async def part(ctx):
        seen["guid"] = ctx.company_guid
        seen["counters"] = await ctx.counters("counters_now")
        return PartResult(Outcome.CONFIRMED, "ok")

    await run_probe(_probe({"A": part}), labels=None, client=client, store=store, capture=capture, io=ScriptedIO())
    assert seen == {"guid": "g-1", "counters": {"GUID": "g-1", "AltVchId": "7"}}


async def test_two_parts_switch_company_and_combine(tmp_path):
    fake = FakeTally([A])

    def on_wait(instruction):
        if "company B" in instruction:
            fake.companies = [B]

    async def ok(ctx):
        return PartResult(Outcome.CONFIRMED, "ok")

    async def diff(ctx):
        return PartResult(Outcome.DIFFERENT, "diff", spec_impact="change")

    client, store, capture = make_harness(tmp_path, fake)
    probe = _probe({"A": ok, "B": diff})
    first = await run_probe(probe, labels=["A"], client=client, store=store, capture=capture, io=ScriptedIO())
    assert first is Outcome.PARTIAL
    both = await run_probe(probe, labels=None, client=client, store=store, capture=capture,
                           io=ScriptedIO(on_wait=on_wait))
    assert both is Outcome.DIFFERENT
    assert [h["part"] for h in store.probe_entry(99)["history"]] == ["A"]
```

- [x] **Step 3: Write the failing CLI tests** — `v2/tests/probes/test_cli.py`

```python
from v2.probes.__main__ import main
from v2.probes.core import Outcome, PartResult
from v2.probes.registry import PROBES, load_probe
from v2.probes.report import render_report
from v2.probes.results import ResultsStore


def test_list_shows_every_probe_and_deferred(tmp_path, capsys):
    assert main(["--results", str(tmp_path / "r.json"), "list"]) == 0
    out = capsys.readouterr().out
    for item in PROBES:
        assert f"{item.id:>2}  {item.name}" in out
    assert out.count("⏭ deferred") == 2  # probes 9 and 20


def test_run_unbuilt_probe_returns_2(tmp_path, capsys):
    assert main(["--results", str(tmp_path / "r.json"), "run", "5"]) == 2
    assert "not built yet" in capsys.readouterr().out


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
        assert sorted(probe.parts) == sorted(item.companies.split("+"))


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


def test_report_command_writes_file(tmp_path):
    out = tmp_path / "report.md"
    assert main(["--results", str(tmp_path / "r.json"), "report", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8").startswith("# S0 probe results")
```

- [x] **Step 4: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_runner.py v2/tests/probes/test_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'v2.probes.companies'` / `'v2.probes.runner'`.

- [x] **Step 5: Write `v2/probes/companies.py`**

```python
"""Probe companies (S0 spec §4). One company is open in Tally at a time."""

COMPANIES: dict[str, str] = {
    "A": "Bharat Traders Probe Copy",
    "B": "Sharma & Sons' Probe Traders",
    "C": "Probe Vault Co",
}
SEED_COMPANY = "Bharat Traders Private Limited"
SEED_BACKUP = "seed_data/TDBK1800_100003.001"
```

- [x] **Step 6: Write `v2/probes/console.py`**

```python
"""How the runner talks to the person at the Tally UI."""
from __future__ import annotations

from typing import Protocol


class ProbeIO(Protocol):
    interactive: bool

    def wait(self, instruction: str) -> None: ...

    def ask(self, prompt: str) -> str: ...

    def say(self, message: str) -> None: ...


class ConsoleIO:
    def __init__(self, interactive: bool = True):
        self.interactive = interactive

    def wait(self, instruction: str) -> None:
        input(f"\n>>> {instruction}\n    Press Enter when done... ")

    def ask(self, prompt: str) -> str:
        return input(f"\n>>> {prompt}\n    > ").strip()

    def say(self, message: str) -> None:
        print(message, flush=True)
```

- [x] **Step 7: Write `v2/probes/context.py`**

```python
"""ProbeContext: what a probe part uses to talk to Tally and record findings (S0 spec §5.2)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from v2.agent.tally.client import TallyClient, TallyResponse
from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER, build_company_list, esc
from v2.agent.tally.exceptions import TallyConnectionError, TallyResponseError, TallyTimeoutError
from v2.agent.tally.xml_utils import parse_company_list, read_objects, sanitize_xml
from v2.probes.capture import Capture
from v2.probes.console import ProbeIO
from v2.probes.core import Probe, ProbeBlocked
from v2.probes.results import ResultsStore
from v2.probes.safety import check_request

POPUP_HINT = "Check Tally for an open popup or modal and dismiss it (LESSONS §15 rule 10)."


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def select_company(text: str, company: str, fields: list[str]) -> dict[str, str]:
    """The `fields` of `company`'s row in a Company collection response."""
    for row in read_objects(text, "COMPANY", ["Name", *fields]):
        if row["Name"] == company:
            return {field: row[field] for field in fields}
    raise ProbeBlocked(f"No row for {company!r} in the company response")


class ProbeContext:
    def __init__(self, *, probe: Probe, part: str, company_name: str, client: TallyClient,
                 store: ResultsStore, capture: Capture, io: ProbeIO):
        self.probe = probe
        self.part = part
        self.company_name = company_name
        self.client = client
        self.store = store
        self.capture = capture
        self.io = io
        self.company_guid: str | None = None
        self.observations: dict[str, Any] = {}
        self.fixtures: list[str] = []
        self.manual_steps: list[dict[str, Any]] = []

    async def try_send(self, step: str, xml: str, timeout: float | None = None) -> tuple[str | None, dict | None]:
        """Guard → send → capture. Returns (sanitized text, None) or (None, {"kind", "message"}) on a transport error."""
        check_request(xml)
        common = dict(probe_id=self.probe.id, part=self.part, step=step, company_name=self.company_name,
                      company_guid=self.company_guid, request_xml=xml, sent_at=datetime.now().astimezone(),
                      environment=dict(self.store.environment))
        try:
            response: TallyResponse = await self.client.post_xml(xml, timeout=timeout)
        except (TallyConnectionError, TallyResponseError) as exc:
            if isinstance(exc, TallyTimeoutError):
                kind = "timeout"
            elif isinstance(exc, TallyConnectionError):
                kind = "refused"
            else:
                kind = "http"
            error = {"kind": kind, "message": str(exc)}
            self.fixtures.append(self.capture.save(**common, error=error) + ".json")
            return None, error
        self.fixtures.append(self.capture.save(**common, response=response))
        return sanitize_xml(response.text), None

    async def send(self, step: str, xml: str, timeout: float | None = None) -> str:
        """Like try_send, but a transport error blocks the part."""
        text, error = await self.try_send(step, xml, timeout)
        if error is None:
            return text
        if error["kind"] == "timeout":
            raise ProbeBlocked(f"{step}: {error['message']}. {POPUP_HINT}")
        if error["kind"] == "refused":
            raise ProbeBlocked(f"{step}: Tally not reachable ({error['message']})")
        raise ProbeBlocked(f"{step}: {error['message']}")

    async def _post_uncaptured(self, xml: str, what: str) -> str:
        check_request(xml)
        try:
            response = await self.client.post_xml(xml)
        except TallyTimeoutError as exc:
            raise ProbeBlocked(f"{what}: {exc}. {POPUP_HINT}") from exc
        except TallyConnectionError as exc:
            raise ProbeBlocked(f"{what}: Tally not reachable ({exc})") from exc
        except TallyResponseError as exc:
            raise ProbeBlocked(f"{what}: {exc}") from exc
        return sanitize_xml(response.text)

    async def company_names(self) -> list[str]:
        """Loaded companies via the company list (guard use; not captured as a fixture)."""
        return parse_company_list(await self._post_uncaptured(build_company_list(), "company list"))

    async def counters(self, step: str | None = None) -> dict[str, str]:
        """Company counters via the request probe 1 confirmed. Captured only when `step` is given."""
        confirmed = self.store.confirmed("company_counters")
        if confirmed is None:
            raise ProbeBlocked("Company counters aren't confirmed yet. Run probe 1 first.")
        xml = confirmed["xml_template"].replace(COMPANY_PLACEHOLDER, esc(self.company_name))
        text = await self.send(step, xml) if step else await self._post_uncaptured(xml, "counters")
        return select_company(text, self.company_name, confirmed["fields"])

    def pause(self, instruction: str) -> None:
        if not self.io.interactive:
            raise ProbeBlocked(f"Needs a manual step: {instruction}")
        self.io.wait(instruction)
        self.manual_steps.append({"n": len(self.manual_steps) + 1, "instruction": instruction, "done_at": _now()})

    def ask(self, prompt: str) -> str:
        if not self.io.interactive:
            raise ProbeBlocked(f"Needs a manual step: {prompt}")
        answer = self.io.ask(prompt)
        self.manual_steps.append({"n": len(self.manual_steps) + 1, "instruction": prompt, "input": answer,
                                  "done_at": _now()})
        return answer

    def observe(self, key: str, value: Any) -> None:
        self.observations[key] = value

    def confirm_request(self, name: str, xml_template: str, **extra: Any) -> None:
        self.store.confirm_request(name, self.probe.id, xml_template, **extra)
```

- [x] **Step 8: Write `v2/probes/runner.py`**

```python
"""Run probe parts: guard → prerequisites → part → record (S0 spec §5.3, §6)."""
from __future__ import annotations

from datetime import datetime

from v2.agent.tally.client import TallyClient
from v2.probes.capture import Capture
from v2.probes.companies import COMPANIES
from v2.probes.console import ProbeIO
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe, ProbeBlocked
from v2.probes.registry import load_probe
from v2.probes.results import ResultsStore
from v2.probes.safety import GuardError, check_company


def _check_requires(probe: Probe, store: ResultsStore) -> None:
    missing = [r for r in probe.requires if store.outcome(r) not in (Outcome.CONFIRMED, Outcome.DIFFERENT)]
    if missing:
        raise ProbeBlocked(f"Run probe(s) {', '.join(map(str, missing))} first.")


def _switch(io: ProbeIO, label: str) -> None:
    instruction = f"Switch Tally to company {label}: {COMPANIES[label]!r} — close every other company."
    if io.interactive:
        io.wait(instruction)
    else:
        io.say(f"(non-interactive) assuming: {instruction}")


async def run_probe(probe: Probe, *, labels: list[str] | None, client: TallyClient, store: ResultsStore,
                    capture: Capture, io: ProbeIO) -> Outcome:
    all_parts = list(probe.parts)
    labels = labels or all_parts
    outcome = store.outcome(probe.id) or Outcome.PARTIAL
    for index, label in enumerate(labels):
        if label not in probe.parts:
            raise ValueError(f"Probe {probe.id} has no part {label!r} (has {', '.join(all_parts)})")
        if index > 0:
            _switch(io, label)
        ctx = ProbeContext(probe=probe, part=label, company_name=COMPANIES[label], client=client,
                           store=store, capture=capture, io=io)
        io.say(f"--- probe {probe.id} ({probe.name}) part {label}: {COMPANIES[label]}")
        try:
            _check_requires(probe, store)
            if probe.guard:
                check_company(await ctx.company_names(), ctx.company_name, mutating=probe.mutating)
                if store.confirmed("company_counters"):
                    ctx.company_guid = (await ctx.counters()).get("GUID") or None
            result = await probe.parts[label](ctx)
        except (ProbeBlocked, GuardError) as exc:
            result = PartResult(Outcome.BLOCKED, str(exc))
        result.observations = {**ctx.observations, **result.observations}
        outcome = store.record_part(probe.id, label, result, all_parts=all_parts, fixtures=ctx.fixtures,
                                    manual_steps=ctx.manual_steps, ran_at=datetime.now().astimezone())
        io.say(f"    part {label}: {result.outcome.value} — {result.summary}")
    return outcome


async def run_order(order: list[tuple[int, str]], *, client: TallyClient, store: ResultsStore,
                    capture: Capture, io: ProbeIO) -> None:
    current: str | None = None
    for probe_id, label in order:
        probe = load_probe(probe_id)
        if probe is None:
            io.say(f"--- probe {probe_id}: not built yet, skipped")
            continue
        if label != current and probe.guard:
            _switch(io, label)
        current = label
        await run_probe(probe, labels=[label], client=client, store=store, capture=capture, io=io)
```

- [x] **Step 9: Write `v2/probes/registry.py`**

```python
"""Every S0 probe (built or not), and the run orders from the S0 spec §6."""
from __future__ import annotations

import importlib
from dataclasses import dataclass

from v2.probes.core import Probe


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

FIRST_ORDER: list[tuple[int, str]] = [
    (0, "A"), (2, "A"), (1, "A"), (16, "A"), (17, "A"), (18, "A"), (21, "B"), (16, "B"), (18, "B"),
]

ALL_ORDER: list[tuple[int, str]] = [
    (0, "A"), (2, "A"), (1, "A"),
    (16, "A"), (17, "A"), (18, "A"), (19, "A"),
    (3, "A"), (4, "A"), (6, "A"), (12, "A"), (23, "A"), (25, "A"),
    (7, "A"), (8, "A"), (10, "A"), (13, "A"),
    (21, "B"), (16, "B"), (18, "B"), (5, "B"), (3, "B"), (11, "B"), (14, "B"), (15, "B"), (22, "B"), (23, "B"), (25, "B"),
    (24, "C"),
]


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

- [x] **Step 10: Write `v2/probes/report.py`**

```python
"""The readable results doc, generated from results.json only (S0 spec §5.7)."""
from __future__ import annotations

from v2.probes.registry import PROBES
from v2.probes.results import ResultsStore


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
    for key in ("wine", "tally_version", "edition", "licence"):
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
        lines.append(f"| {item.id} | {item.name} | {item.companies} | {entry['outcome']} | {_cell(summary)} | "
                     f"{_cell(impact) or '—'} |")
    lines += ["", "## Deferred (tier C, Q29)", ""]
    lines += [f"- Probe {item.id} — {item.name}" for item in PROBES if item.deferred]
    lines.append("- Probe 21's timing half, and the standard-edition runs of probes 7 and 13")
    return "\n".join(lines) + "\n"
```

- [x] **Step 11: Write `v2/probes/__main__.py`**

```python
"""Runner CLI: python -m v2.probes {list,run,report} (S0 spec §5.3)."""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

import httpx

from v2.agent.tally.client import TallyClient
from v2.probes.capture import Capture
from v2.probes.console import ConsoleIO, ProbeIO
from v2.probes.registry import ALL_ORDER, FIRST_ORDER, PROBES, load_probe
from v2.probes.report import render_report
from v2.probes.results import ResultsStore
from v2.probes.runner import run_order, run_probe

V2_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = V2_ROOT / "probes" / "results" / "results.json"
FIXTURES_DIR = V2_ROOT / "tests" / "fixtures" / "sync"
DOCS_DIR = V2_ROOT.parent / "docs"


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
    report = sub.add_parser("report")
    report.add_argument("--out", type=Path)
    return parser


def _status(store: ResultsStore, item) -> str:
    if item.deferred:
        return "⏭ deferred (Q29)"
    outcome = store.outcome(item.id)
    if outcome is not None:
        return outcome.value
    return "not run" if item.module else "not built"


def _list(store: ResultsStore) -> int:
    for item in PROBES:
        print(f"{item.id:>2}  {item.name:<28} {item.companies:<5} {item.tier:<4} {_status(store, item)}")
    return 0


async def _run(args, store: ResultsStore, transport: httpx.AsyncBaseTransport | None, io: ProbeIO) -> int:
    client = TallyClient(args.host, args.port, transport=transport)
    capture = Capture(args.fixtures)
    try:
        if args.first or args.all:
            await run_order(FIRST_ORDER if args.first else ALL_ORDER, client=client, store=store, capture=capture, io=io)
            return 0
        probe = load_probe(args.probe_id)
        if probe is None:
            print(f"Probe {args.probe_id} is not built yet (S0 plan part 2 or 3).")
            return 2
        labels = [args.company] if args.company else None
        await run_probe(probe, labels=labels, client=client, store=store, capture=capture, io=io)
        return 0
    finally:
        await client.close()


def main(argv: list[str] | None = None, *, transport: httpx.AsyncBaseTransport | None = None,
         io: ProbeIO | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = ResultsStore(args.results)
    if args.command == "list":
        return _list(store)
    if args.command == "report":
        out = args.out or DOCS_DIR / f"bi-s0-probe-results-{date.today().isoformat()}.md"
        out.write_text(render_report(store, date.today().isoformat()), encoding="utf-8")
        print(f"Wrote {out}")
        return 0
    return asyncio.run(_run(args, store, transport, io or ConsoleIO(interactive=not args.non_interactive)))


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 12: Run the tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: runner + CLI tests pass **except** `test_registry_matches_built_modules`, which fails with
`ModuleNotFoundError: No module named 'v2.probes.p00_environment'` until Tasks 6–8 add the three probe modules.
If any other test fails, fix it before moving on.

---

### Task 6: Anchors + probe 0 (environment, makes company A)

**Files:**
- Create: `v2/probes/anchors.py`, `v2/probes/p00_environment.py`
- Test: `v2/tests/probes/test_p00_environment.py`

**Interfaces:**
- Consumes: `ProbeContext`, `wrap_report`, `wrap_collection`, `build_company_list`, `parse_bills`, `parse_trial_balance`, `read_objects`
- Produces:
  - `anchors`: `SEED_RECEIVABLE = Decimal("970537.00")`, `SEED_PAYABLE = Decimal("1834142.00")`, `ANCHOR_FROM = "01-04-2025"`,
    `ANCHOR_DATE = "31-03-2026"`, `AnchorResult(receivable, payable, tb_rows: dict[str, str], problems: list[str])` with `.ok`,
    `async check_anchors(ctx, step_prefix: str, tb_baseline: dict[str, str] | None) -> AnchorResult`
  - `p00_environment`: `PROBE` (id 0, part "A", `guard=False`), `wine_version() -> str | None`, `GUID_REQUEST`
  - Side effects in `results.json` environment: `wine`, `tally_version`, `edition`, `licence`, `recorded_by_probe`,
    `company_a_tb_baseline`

- [x] **Step 1: Write the failing tests** — `v2/tests/probes/test_p00_environment.py`

```python
from v2.probes import p00_environment
from v2.probes.companies import COMPANIES, SEED_COMPANY
from v2.probes.core import Outcome
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import FakeTally, ScriptedIO, bills_xml, make_harness, objects_xml, tb_xml

A = COMPANIES["A"]
RECEIVABLE = bills_xml([("S015", "Apex Technologies Pvt Ltd", "-62800.00"), ("S010", "Rest", "-907737.00")])
PAYABLE = bills_xml([("P001", "Samsung India Electronics", "243100.00"), ("P004", "Rest", "1591042.00")])
TB = tb_xml([("Capital Account", "", "100000.00"), ("Current Assets", "-100000.00", "")])


def _fake(receivable=RECEIVABLE):
    fake = FakeTally([])
    fake.route("S0CompanyGuid", lambda body: objects_xml(
        "COMPANY", [{"Name": fake.companies[0], "GUID": "guid-seed"}] if fake.companies else []))
    fake.route("<ID>Bills Receivable</ID>", lambda body: receivable)
    fake.route("<ID>Bills Payable</ID>", lambda body: PAYABLE)
    fake.route("<ID>Trial Balance</ID>", lambda body: TB)
    return fake


def _io(fake, answers=("TallyPrime 7.0", "Edit Log", "licensed")):
    def on_wait(instruction):
        if instruction.startswith("Restore"):
            fake.companies = [SEED_COMPANY]
        elif "rename it to" in instruction:
            fake.companies = [A]

    return ScriptedIO(answers=list(answers), on_wait=on_wait)


async def _run(tmp_path, fake, io, monkeypatch, wine="wine-9.0"):
    monkeypatch.setattr(p00_environment, "wine_version", lambda: wine)
    client, store, capture = make_harness(tmp_path, fake)
    outcome = await run_probe(p00_environment.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return outcome, store


async def test_happy_path_makes_company_a(tmp_path, monkeypatch):
    fake = _fake()
    outcome, store = await _run(tmp_path, fake, _io(fake), monkeypatch)
    part = store.probe_entry(0)["parts"]["A"]
    assert outcome is Outcome.CONFIRMED, part["summary"]
    assert store.environment["wine"] == "wine-9.0"
    assert store.environment["licence"] == "licensed"
    assert store.environment["company_a_tb_baseline"] == {"Capital Account": "100000.00", "Current Assets": "-100000.00"}
    assert part["observations"]["guid_changed_on_rename"] is False
    assert part["fixtures"] == [
        "p00_A_company_list.xml", "p00_A_guid_before_rename.xml", "p00_A_guid_after_rename.xml",
        "p00_A_anchors_bills_receivable.xml", "p00_A_anchors_bills_payable.xml", "p00_A_anchors_tb.xml",
    ]


async def test_tally_unreachable_fails_with_q29_impact(tmp_path, monkeypatch):
    fake = _fake()
    fake.down = True
    outcome, store = await _run(tmp_path, fake, _io(fake), monkeypatch)
    part = store.probe_entry(0)["parts"]["A"]
    assert outcome is Outcome.FAILED
    assert "Q29" in part["spec_impact"]


async def test_anchor_mismatch_blocks(tmp_path, monkeypatch):
    fake = _fake(receivable=bills_xml([("S015", "Apex", "-1.00")]))
    outcome, store = await _run(tmp_path, fake, _io(fake), monkeypatch)
    part = store.probe_entry(0)["parts"]["A"]
    assert outcome is Outcome.BLOCKED
    assert "Bills Receivable" in part["summary"]
    assert "company_a_tb_baseline" not in store.environment


async def test_wrong_company_after_restore_blocks(tmp_path, monkeypatch):
    fake = _fake()
    io = ScriptedIO(on_wait=lambda instruction: setattr(fake, "companies", ["Something Else"]))
    outcome, store = await _run(tmp_path, fake, io, monkeypatch)
    assert outcome is Outcome.BLOCKED
    assert SEED_COMPANY in store.probe_entry(0)["parts"]["A"]["summary"]


async def test_missing_wine_asks_for_version(tmp_path, monkeypatch):
    fake = _fake()
    io = _io(fake, answers=("wine-8.0 (typed)", "TallyPrime 7.0", "Edit Log", "licensed"))
    outcome, store = await _run(tmp_path, fake, io, monkeypatch, wine=None)
    assert outcome is Outcome.CONFIRMED
    assert store.environment["wine"] == "wine-8.0 (typed)"
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p00_environment.py -q`
Expected: FAIL — `ImportError: cannot import name 'p00_environment'`.

- [x] **Step 3: Write `v2/probes/anchors.py`**

```python
"""Is company A still the seed company's known state? (S0 spec §4.2)

Bills totals come from docs/seed-data-setup.md. The TB rows are compared with the baseline probe 0 captured
right after the restore (tests/fixtures/trial_balance_live.xml is another company and is never used here).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from v2.agent.tally.envelopes import wrap_report
from v2.agent.tally.reports import parse_bills, parse_trial_balance
from v2.probes.context import ProbeContext

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


async def check_anchors(ctx: ProbeContext, step_prefix: str, tb_baseline: dict[str, str] | None) -> AnchorResult:
    company = ctx.company_name
    receivable = _bills_total(await ctx.send(
        f"{step_prefix}_bills_receivable", wrap_report("Bills Receivable", ANCHOR_DATE, ANCHOR_DATE, company)))
    payable = _bills_total(await ctx.send(
        f"{step_prefix}_bills_payable", wrap_report("Bills Payable", ANCHOR_DATE, ANCHOR_DATE, company)))
    tb_text = await ctx.send(f"{step_prefix}_tb", wrap_report("Trial Balance", ANCHOR_FROM, ANCHOR_DATE, company))
    tb_rows = {row["account_name"]: str(row["closing_balance"]) for row in parse_trial_balance(tb_text)}
    result = AnchorResult(receivable=receivable, payable=payable, tb_rows=tb_rows)
    if receivable != SEED_RECEIVABLE:
        result.problems.append(f"Bills Receivable {receivable} ≠ {SEED_RECEIVABLE}")
    if payable != SEED_PAYABLE:
        result.problems.append(f"Bills Payable {payable} ≠ {SEED_PAYABLE}")
    if tb_baseline is not None and tb_rows != tb_baseline:
        result.problems.append("TB group rows differ from probe 0's baseline")
    return result
```

- [x] **Step 4: Write `v2/probes/p00_environment.py`**

```python
"""Probe 0 — environment check; makes company A (S0 spec §7 "Probe 0")."""
from __future__ import annotations

import subprocess

from v2.agent.tally.envelopes import build_company_list, wrap_collection
from v2.agent.tally.xml_utils import read_objects
from v2.probes.anchors import check_anchors
from v2.probes.companies import COMPANIES, SEED_BACKUP, SEED_COMPANY
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe

GUID_REQUEST = wrap_collection("S0CompanyGuid", "Company", ["Name", "GUID"])


def wine_version() -> str | None:
    try:
        done = subprocess.run(["wine", "--version"], capture_output=True, text=True, timeout=15)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() or None


async def _guid(ctx: ProbeContext, step: str) -> str:
    rows = read_objects(await ctx.send(step, GUID_REQUEST), "COMPANY", ["Name", "GUID"])
    return rows[0]["GUID"] if len(rows) == 1 else ""


async def run_a(ctx: ProbeContext) -> PartResult:
    ctx.company_name = SEED_COMPANY
    wine = wine_version() or ctx.ask("`wine --version` didn't run here. Type the Wine version:")
    ctx.observe("wine", wine)

    ctx.pause("Start TallyPrime under Wine (README.md 'Installing TallyPrime on macOS') with the XML server on port 9000.")
    _, error = await ctx.try_send("company_list", build_company_list())
    if error is not None:
        return PartResult(Outcome.FAILED, f"Tally didn't answer on port 9000 ({error['kind']})",
                          spec_impact="S0 can't run under Wine on this Mac; S0 is blocked on Q29 (tier C machine).")

    ctx.pause(f"Restore {SEED_BACKUP} into a NEW, separate Tally data folder (not Bharat Traders' usual folder). "
              f"Open only that company and close every other company.")
    names = await ctx.company_names()
    if names != [SEED_COMPANY]:
        return PartResult(Outcome.BLOCKED, f"Expected only {SEED_COMPANY!r} open after the restore, got {names}")
    guid_before = await _guid(ctx, "guid_before_rename")

    ctx.pause(f"In Tally, alter this company (Company menu, Alt+K → Alter) and rename it to {COMPANIES['A']!r}. Keep it open.")
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

    tally_version = ctx.ask("Tally version (Help → About, e.g. 'TallyPrime 7.0'):")
    edition = ctx.ask("Edition — type 'Edit Log' or 'standard':")
    licence = ctx.ask("Licence mode — type 'licensed' or 'educational':").lower()
    ctx.store.update_environment(wine=wine, tally_version=tally_version, edition=edition, licence=licence,
                                 recorded_by_probe=0)

    anchors = await check_anchors(ctx, "anchors", tb_baseline=None)
    ctx.observe("anchors", {"receivable": anchors.receivable, "payable": anchors.payable, "tb_rows": anchors.tb_rows})
    if not anchors.ok:
        return PartResult(Outcome.BLOCKED, "Restored company doesn't match the seed figures: "
                          + "; ".join(anchors.problems) + ". Re-restore the seed backup.")
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

- [x] **Step 5: Run the tests**

Run: `uv run --project v2 pytest v2/tests/probes/test_p00_environment.py -q`
Expected: `5 passed`.

---

### Task 7: Probe 2 (cheapest active-company GUID read)

**Files:**
- Create: `v2/probes/p02_active_company_guid.py`
- Test: `v2/tests/probes/test_p02_active_company_guid.py`

**Interfaces:**
- Consumes: `ProbeContext.try_send`, `pause`, `observe`, `confirm_request`; `wrap_collection`, `COMPANY_PLACEHOLDER`, `esc`, `read_objects`
- Produces: `PROBE` (id 2, part "A"), `CANDIDATES: dict[str, str]` (keys `"a"`, `"b"`, `"c"`);
  `results.json` `confirmed_requests.active_company = {"probe": 2, "xml_template": …, "candidate": "a"|"b"|"c"}`

- [x] **Step 1: Write the failing tests** — `v2/tests/probes/test_p02_active_company_guid.py`

```python
from v2.probes import p02_active_company_guid as p02
from v2.probes.companies import COMPANIES
from v2.probes.core import Outcome
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import FakeTally, ScriptedIO, make_harness, objects_xml

A = COMPANIES["A"]
EMPTY = "<ENVELOPE></ENVELOPE>"


def _row(fake, extra=None, ignore_state=False):
    def handler(body):
        if not fake.companies and not ignore_state:
            return objects_xml("COMPANY", [])
        return objects_xml("COMPANY", [{"Name": A, "GUID": "g-1", **(extra or {})}])
    return handler


def _io(fake):
    def on_wait(instruction):
        if instruction.startswith("Close every company"):
            fake.companies = []
        elif instruction.startswith("Open company"):
            fake.companies = [A]
    return ScriptedIO(on_wait=on_wait)


async def _run(tmp_path, fake):
    client, store, capture = make_harness(tmp_path, fake)
    outcome = await run_probe(p02.PROBE, labels=None, client=client, store=store, capture=capture, io=_io(fake))
    return outcome, store


async def test_cheapest_candidate_confirmed(tmp_path):
    fake = FakeTally([A])
    fake.route("S0ActiveCompany", _row(fake))
    fake.route("<TYPE>Object</TYPE>", _row(fake, extra={"Padding": "x" * 300}))
    fake.route("S0CompanyListGuid", _row(fake))
    outcome, store = await _run(tmp_path, fake)
    part = store.probe_entry(2)["parts"]["A"]
    assert outcome is Outcome.CONFIRMED, part["summary"]
    assert store.confirmed("active_company")["candidate"] == "a"
    assert part["observations"]["no_company_distinguishable"] is True
    assert "p02_A_active_a_no_company.xml" in part["fixtures"]


async def test_only_full_list_works_is_different(tmp_path):
    fake = FakeTally([A])
    fake.route("S0ActiveCompany", lambda body: EMPTY)
    fake.route("<TYPE>Object</TYPE>", lambda body: EMPTY)
    fake.route("S0CompanyListGuid", _row(fake))
    outcome, store = await _run(tmp_path, fake)
    assert outcome is Outcome.DIFFERENT
    assert store.confirmed("active_company")["candidate"] == "c"
    assert "company list" in store.probe_entry(2)["parts"]["A"]["spec_impact"]


async def test_no_candidate_works_fails(tmp_path):
    fake = FakeTally([A])
    outcome, store = await _run(tmp_path, fake)
    assert outcome is Outcome.FAILED
    assert store.confirmed("active_company") is None


async def test_guid_still_returned_with_no_company_is_different(tmp_path):
    fake = FakeTally([A])
    fake.route("S0ActiveCompany", _row(fake, ignore_state=True))
    outcome, store = await _run(tmp_path, fake)
    part = store.probe_entry(2)["parts"]["A"]
    assert outcome is Outcome.DIFFERENT
    assert part["observations"]["no_company_distinguishable"] is False
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p02_active_company_guid.py -q`
Expected: FAIL — `ImportError: cannot import name 'p02_active_company_guid'`.

- [x] **Step 3: Write `v2/probes/p02_active_company_guid.py`**

```python
"""Probe 2 — cheapest correct read of the active company's GUID, and the no-company response (S0 spec §7).

The chosen read is for the S2 agent's per-cycle gate; the harness guard keeps using the company list.
"""
from __future__ import annotations

from v2.agent.tally.envelopes import COMPANY_PLACEHOLDER, esc, wrap_collection
from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext
from v2.probes.core import Outcome, PartResult, Probe

CANDIDATES: dict[str, str] = {
    "a": wrap_collection("S0ActiveCompany", "Company", ["Name", "GUID"],
                         filters=[("S0IsActive", "$Name = ##SVCurrentCompany")]),
    "b": f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Object</TYPE>
<SUBTYPE>Company</SUBTYPE>
<ID TYPE="Name">{COMPANY_PLACEHOLDER}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<FETCHLIST>
<FETCH>Name</FETCH>
<FETCH>GUID</FETCH>
</FETCHLIST>
</DESC>
</BODY>
</ENVELOPE>""",
    "c": wrap_collection("S0CompanyListGuid", "Company", ["Name", "GUID"]),
}


def _reading(text: str | None) -> dict:
    if text is None:
        return {"rows": 0, "name": "", "guid": ""}
    rows = [r for r in read_objects(text, "COMPANY", ["Name", "GUID"]) if r["Name"] or r["GUID"]]
    one = rows[0] if len(rows) == 1 else {"Name": "", "GUID": ""}
    return {"rows": len(rows), "name": one["Name"], "guid": one["GUID"]}


async def run_a(ctx: ProbeContext) -> PartResult:
    results: dict[str, dict] = {}
    for key, template in CANDIDATES.items():
        text, error = await ctx.try_send(f"active_{key}", template.replace(COMPANY_PLACEHOLDER, esc(ctx.company_name)))
        reading = _reading(text)
        correct = error is None and reading["rows"] == 1 and reading["name"] == ctx.company_name and bool(reading["guid"])
        results[key] = {"correct": correct, "bytes": len(text.encode("utf-8")) if text else 0, "error": error, **reading}
    ctx.observe("candidates", results)

    guids = {r["guid"] for r in results.values() if r["correct"]}
    if len(guids) > 1:
        return PartResult(Outcome.BLOCKED, f"Candidates disagree on the GUID ({sorted(guids)}); investigate by hand")
    cheap = sorted((results[k]["bytes"], k) for k in ("a", "b") if results[k]["correct"])
    chosen = cheap[0][1] if cheap else ("c" if results["c"]["correct"] else None)
    if chosen is None:
        return PartResult(Outcome.FAILED, "No candidate returned our company's GUID",
                          spec_impact="No way found to read the company GUID over XML: Part 1 decision 4 / R2 "
                                      "(GUID check) need another identity signal before S2.")
    ctx.confirm_request("active_company", CANDIDATES[chosen], candidate=chosen)
    ctx.observe("company_guid", results[chosen]["guid"])

    ctx.pause("Close every company in Tally (keep Tally running): Company menu (Alt+K) → Shut Company, until none is open.")
    no_company: dict[str, dict] = {}
    for key, template in CANDIDATES.items():
        text, error = await ctx.try_send(f"active_{key}_no_company",
                                         template.replace(COMPANY_PLACEHOLDER, esc(ctx.company_name)))
        no_company[key] = {"error": error, **_reading(text), "snippet": (text or "")[:400]}
    ctx.observe("no_company", no_company)
    distinguishable = no_company[chosen]["error"] is not None or not no_company[chosen]["guid"]
    ctx.observe("no_company_distinguishable", distinguishable)
    ctx.pause(f"Open company {ctx.company_name!r} again (only that one).")

    if not distinguishable:
        return PartResult(Outcome.DIFFERENT, f"Candidate ({chosen}) still returns a GUID with no company open",
                          spec_impact="The S2 gate must also check the company list before trusting the GUID read "
                                      "(Part 1 §5 gate.py).")
    if chosen == "c":
        return PartResult(Outcome.DIFFERENT, "Only the full company list returns the GUID",
                          spec_impact="No cheap active-company read: the S2 gate reads the company list (heavier) "
                                      "every cycle (Part 1 §5 gate.py).")
    return PartResult(Outcome.CONFIRMED, f"Candidate ({chosen}) returns the GUID in {results[chosen]['bytes']} bytes; "
                                         "the no-company response is distinguishable")


PROBE = Probe(
    id=2,
    name="active_company_guid",
    question="What is the cheapest read of the active company's GUID, and what comes back with no company open?",
    feeds=("decision 4", "R2"),
    parts={"A": run_a},
)
```

- [x] **Step 4: Run the tests**

Run: `uv run --project v2 pytest v2/tests/probes/test_p02_active_company_guid.py -q`
Expected: `4 passed`.

---

### Task 8: Probe 1 (which counters move on which change)

**Files:**
- Create: `v2/probes/p01_company_counters.py`
- Test: `v2/tests/probes/test_p01_company_counters.py`

**Interfaces:**
- Consumes: `ProbeContext.send`, `counters`, `pause`, `ask`, `observe`, `confirm_request`; `select_company`;
  `wrap_collection`, `formula_string`, `read_objects`
- Produces: `PROBE` (id 1, part "A"), `CANDIDATE_FIELDS`, `COUNTERS_REQUEST`, `ACTIONS`;
  `results.json` `confirmed_requests.company_counters = {"probe": 1, "xml_template": COUNTERS_REQUEST, "fields": [...]}`
  (used by every later probe through `ctx.counters()`)

- [x] **Step 1: Write the failing tests** — `v2/tests/probes/test_p01_company_counters.py`

```python
from v2.probes import p01_company_counters as p01
from v2.probes.companies import COMPANIES
from v2.probes.core import Outcome
from v2.probes.runner import run_probe
from v2.tests.probes.fakes import FakeTally, ScriptedIO, make_harness, objects_xml

A = COMPANIES["A"]


def _fake(state, include_counters=True):
    fake = FakeTally([A])

    def counters(body):
        row = {"Name": A, "GUID": "g-1", "BooksFrom": "20250401", "LastVoucherDate": "20260301", "AlterID": "1"}
        if include_counters:
            row.update(AltVchId=str(state["AltVchId"]), AltMstId=str(state["AltMstId"]))
        return objects_xml("COMPANY", [row])

    fake.route("S0CompanyCounters", counters)
    fake.route("S0LedgerList", lambda body: objects_xml("LEDGER", [
        {"Name": "Cash", "Parent": "Cash-in-Hand"}, {"Name": "Bank Charges", "Parent": "Indirect Expenses"}]))
    fake.route("S0OneLedger", lambda body: objects_xml("LEDGER", [
        {"Name": "Bank Charges", "GUID": "l-1", "AlterID": str(state["ledger"])}]))
    return fake


def _io(state, skip=(), voucher_moves_ledger=False):
    effects = {
        "Create a Payment": ("AltVchId",), "Alter that voucher": ("AltVchId",), "Delete that voucher": ("AltVchId",),
        "Alter ledger": ("AltMstId", "ledger"), "Create a ledger": ("AltMstId",), "Delete ledger": ("AltMstId",),
    }

    def on_wait(instruction):
        for prefix, fields in effects.items():
            if instruction.startswith(prefix) and prefix not in skip:
                for field in fields:
                    state[field] += 1
                if prefix == "Create a Payment" and voucher_moves_ledger:
                    state["ledger"] += 1

    return ScriptedIO(on_wait=on_wait)


async def _run(tmp_path, fake, io):
    client, store, capture = make_harness(tmp_path, fake)
    outcome = await run_probe(p01.PROBE, labels=None, client=client, store=store, capture=capture, io=io)
    return outcome, store


def _state():
    return {"AltVchId": 100, "AltMstId": 50, "ledger": 7}


async def test_expected_counters_confirmed_and_request_stored(tmp_path):
    state = _state()
    outcome, store = await _run(tmp_path, _fake(state), _io(state))
    part = store.probe_entry(1)["parts"]["A"]
    assert outcome is Outcome.CONFIRMED, part["summary"]
    confirmed = store.confirmed("company_counters")
    assert confirmed["xml_template"] == p01.COUNTERS_REQUEST
    assert confirmed["fields"] == ["GUID", "AltVchId", "AltMstId", "BooksFrom", "LastVoucherDate", "AlterID"]
    assert part["observations"]["ledger"] == "Bank Charges"
    assert part["observations"]["matrix"]["delete_voucher"]["moved"]["AltVchId"] is True
    assert part["observations"]["ledger_alterid_moved_on_voucher_entry"] is False
    assert "p01_A_counters_after_delete_ledger.xml" in part["fixtures"]


async def test_counter_not_moving_is_different(tmp_path):
    state = _state()
    outcome, store = await _run(tmp_path, _fake(state), _io(state, skip=("Delete that voucher",)))
    part = store.probe_entry(1)["parts"]["A"]
    assert outcome is Outcome.DIFFERENT
    assert "AltVchId did not move on delete_voucher" in part["summary"]
    assert "R6" in part["spec_impact"]


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
```

- [x] **Step 2: Run to verify they fail**

Run: `uv run --project v2 pytest v2/tests/probes/test_p01_company_counters.py -q`
Expected: FAIL — `ImportError: cannot import name 'p01_company_counters'`.

- [x] **Step 3: Write `v2/probes/p01_company_counters.py`**

```python
"""Probe 1 — which company counters move on which change (S0 spec §7 "Probe 1").

UI changes are made by the person at Tally when the probe pauses (S0-D3): UI edits are what customers make.
"""
from __future__ import annotations

from v2.agent.tally.envelopes import formula_string, wrap_collection
from v2.agent.tally.xml_utils import read_objects
from v2.probes.context import ProbeContext, select_company
from v2.probes.core import Outcome, PartResult, Probe

CANDIDATE_FIELDS = ["GUID", "AltVchId", "AltMstId", "BooksFrom", "LastVoucherDate", "AlterID"]
COUNTERS_REQUEST = wrap_collection("S0CompanyCounters", "Company", ["Name", *CANDIDATE_FIELDS])
WATCHED = ["AltVchId", "AltMstId", "LastVoucherDate"]
THROWAWAY_LEDGER = "S0 Probe Ledger"

ACTIONS: list[tuple[str, str, str]] = [
    ("create_voucher", "voucher",
     "Create a Payment voucher: Cash → {ledger}, ₹1, narration 'S0-throwaway 1'. Save it."),
    ("alter_voucher", "voucher", "Alter that voucher's amount to ₹2 and save."),
    ("delete_voucher", "voucher", "Delete that voucher (open it, Alt+D)."),
    ("alter_ledger", "master", "Alter ledger '{ledger}': set its Mailing Name to 'S0 probe' and save."),
    ("create_ledger", "master", f"Create a ledger '{THROWAWAY_LEDGER}' under Indirect Expenses."),
    ("delete_ledger", "master", f"Delete ledger '{THROWAWAY_LEDGER}'."),
]


async def _pick_expense_ledger(ctx: ProbeContext) -> str:
    text = await ctx.send("ledger_list", wrap_collection("S0LedgerList", "Ledger", ["Name", "Parent"], ctx.company_name))
    rows = read_objects(text, "LEDGER", ["Name", "Parent"])
    if any(row["Name"] == "Bank Charges" for row in rows):
        return "Bank Charges"
    for row in rows:
        if row["Parent"] == "Indirect Expenses":
            return row["Name"]
    return ctx.ask("Type the name of an expense ledger in this company to use for the ₹1 test voucher:")


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
    previous = await ctx.counters("counters_baseline")
    ledger_before = await _ledger_alterid(ctx, ledger, "ledger_before")
    ledger_after_voucher = ledger_before
    matrix: dict[str, dict] = {}
    for action, kind, instruction in ACTIONS:
        ctx.pause(instruction.format(ledger=ledger))
        current = await ctx.counters(f"counters_after_{action}")
        watched = [field for field in WATCHED if field in present]
        matrix[action] = {
            "kind": kind,
            "moved": {field: current.get(field) != previous.get(field) for field in watched},
            "values": {field: current.get(field) for field in watched},
        }
        if action == "create_voucher":
            ledger_after_voucher = await _ledger_alterid(ctx, ledger, "ledger_after_voucher")
        previous = current
    ctx.observe("matrix", matrix)
    ledger_moved = ledger_before != ledger_after_voucher
    ctx.observe("ledger_alterid_moved_on_voucher_entry", ledger_moved)

    deviations = []
    for action, entry in matrix.items():
        field = "AltVchId" if entry["kind"] == "voucher" else "AltMstId"
        if not entry["moved"].get(field):
            deviations.append(f"{field} did not move on {action}")
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
    mutating=True,
)
```

- [x] **Step 4: Run all v2 tests**

Run: `uv run --project v2 pytest v2/tests -q`
Expected: **all pass**, including `test_registry_matches_built_modules` and `test_v2_tree_has_no_forbidden_imports`.

---

### Task 9: Verify, smoke-run, update docs, review

**Files:**
- Modify: `docs/plans/2026-09-22-bi-part1-tracker.md`, `docs/roadmap.md` (S0 row)
- Create: `docs/code-review-bi-s0-part1-2026-09-22.md`

- [x] **Step 1: Full test run**

Run: `uv run --project v2 pytest v2/tests -q 2>&1 | tail -5`
Expected: all pass, 0 failures. Record the count for the tracker.

- [x] **Step 2: CLI smoke (no Tally needed)**

Run:
```bash
uv run --project v2 python -m v2.probes --results /tmp/s0-smoke/results.json list
uv run --project v2 python -m v2.probes --results /tmp/s0-smoke/results.json report --out /tmp/s0-smoke/report.md
uv run --project v2 python -m v2.probes --results /tmp/s0-smoke/results.json run 5; echo "exit=$?"
```
Expected: 26 rows (0, 1, 2 "not run"; 9 and 20 "⏭ deferred (Q29)"; the rest "not built"); report written;
`run 5` prints "not built yet" and `exit=2`.

- [x] **Step 3: Isolation check against git**

Run: `git status --porcelain | grep -v -E '^\?\? (v2/|docs/)' ; git diff --stat -- . ':!docs'`
Expected: only entries that existed before this plan (pre-existing untracked `scripts/cleanup_*.py`,
`frontend/.tmp_vitest/`, PNGs, `.pgtmp/`, `.playwright-mcp/`, `.tmp_eval/`); `git diff --stat` outside `docs/` is empty.

- [x] **Step 4: Code review** — run the `code-review` skill on `v2/`; store findings in
  `docs/code-review-bi-s0-part1-2026-09-22.md`; fix confirmed findings; re-run Step 1.

- [x] **Step 5: Tracker + roadmap**
  - Tracker §3: row "`v2/` scaffold" ✅ (proof: test count + this plan); probes 0, 1, 2 stay ⬜ but add
    "built (harness-tested), awaiting live run" in Proof. Change log entry.
  - Tracker §0 S0 row: "🟡 Part 1 built; Parts 2–3 + live run next".
  - Roadmap Set C S0 row: same one-line status.

---

## Self-review (done while writing)

- **Spec coverage (S0 spec → task):** §3 layout → T1–T5; §3.1 copies → T2–T3; §4.2 anchors → T6; §4.5 guards → T4/T5;
  §5.1 contract + precedence → T4; §5.2 context → T5; §5.3 CLI → T5; §5.4 outcomes → T4; §5.6 capture → T4;
  §5.7 results + report → T4/T5; §6 orders → T5 `registry`; §7 probes 0/1/2 → T6–T8; §11.1 matrix rows → T4/T5 tests;
  §11.2 copied-code tests → T2/T3; §11.3 isolation → T1/T2. **Not in this part (by design):** probes 3–25, company B
  loader (§4.3), anchors step inside `--all`, §11.4 loader tests → plan parts 2–3.
- **Names used across tasks:** `ProbeContext.try_send/send/counters/company_names/pause/ask/observe/confirm_request`,
  `select_company`, `run_probe(probe, *, labels, client, store, capture, io)`, `ResultsStore.record_part(..., all_parts,
  fixtures, manual_steps, ran_at)`, `COMPANY_PLACEHOLDER`, `COMPANIES`, `check_anchors(ctx, step_prefix, tb_baseline)` —
  consistent in every task that uses them.
