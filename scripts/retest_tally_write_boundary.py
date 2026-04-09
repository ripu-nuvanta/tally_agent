"""
Boundary retest for Tally voucher write date-clamping issue.

Background:
  On 2026-04-05 an exploration script created a Payment voucher with
  DATE=20260405 against live Tally successfully.
  On 2026-04-09 (during B1a smoke test) writes with any DATE > 20260302
  were rejected with a misleading <LINEERROR>"Voucher date is missing"</LINEERROR>.
  Theory: Tally license was not properly activated, clamping its internal
  "current date". License has since been fixed — this script retests the
  boundary.

What this does:
  For each test date in TEST_DATES, attempt a Payment voucher import of
  Rs 1.00 (Debit: Bank Charges, Credit: Cash). If CREATED=1, immediately
  delete via TAGNAME="Master ID" + LASTVCHID. Captures CREATED / ALTERED /
  ERRORS / EXCEPTIONS / LASTVCHID / LINEERROR and prints a summary table.

READ-ONLY w.r.t. masters. Creates + deletes tiny test vouchers only.
"""
from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

import httpx

TALLY_HOST = "localhost"
TALLY_PORT = 9000
COMPANY = "NUVANTA AI TECHNOLOGIES PRIVATE LIMITED"
EXPENSE_LEDGER = "Bank Charges"
CASH_LEDGER = "Cash"
TEST_DATES = ["20260302", "20260303", "20260405", "20260409"]

BASE_URL = f"http://{TALLY_HOST}:{TALLY_PORT}"
TIMEOUT = httpx.Timeout(60.0, connect=5.0)


def build_create_xml(date_yyyymmdd: str) -> str:
    narration = f"B1a retest - license verification - {date_yyyymmdd}"
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>Vouchers</REPORTNAME>
<STATICVARIABLES><SVCURRENTCOMPANY>{COMPANY}</SVCURRENTCOMPANY></STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<VOUCHER VCHTYPE="Payment" ACTION="Create">
<DATE>{date_yyyymmdd}</DATE>
<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
<NARRATION>{narration}</NARRATION>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{EXPENSE_LEDGER}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-1.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{CASH_LEDGER}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>1.00</AMOUNT>
</ALLLEDGERENTRIES.LIST>
</VOUCHER>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA></BODY></ENVELOPE>"""


def build_delete_xml(date_yyyymmdd: str, master_id: str) -> str:
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>Vouchers</REPORTNAME>
<STATICVARIABLES><SVCURRENTCOMPANY>{COMPANY}</SVCURRENTCOMPANY></STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
<VOUCHER DATE="{date_yyyymmdd}" TAGNAME="Master ID" TAGVALUE="{master_id}" VCHTYPE="Payment" ACTION="Delete"/>
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA></BODY></ENVELOPE>"""


@dataclass
class TallyResponse:
    created: int = 0
    altered: int = 0
    deleted: int = 0
    errors: int = 0
    exceptions: int = 0
    last_vch_id: Optional[str] = None
    line_errors: list[str] = field(default_factory=list)
    raw: str = ""


def parse_response(xml_text: str) -> TallyResponse:
    r = TallyResponse(raw=xml_text)
    # Use regex fallback because Tally's response often has odd namespacing
    def _int(tag: str) -> int:
        m = re.search(rf"<{tag}>(-?\d+)</{tag}>", xml_text, re.IGNORECASE)
        return int(m.group(1)) if m else 0

    r.created = _int("CREATED")
    r.altered = _int("ALTERED")
    r.deleted = _int("DELETED")
    r.errors = _int("ERRORS")
    r.exceptions = _int("EXCEPTIONS")
    m = re.search(r"<LASTVCHID>(\d+)</LASTVCHID>", xml_text, re.IGNORECASE)
    if m:
        r.last_vch_id = m.group(1)
    r.line_errors = [
        m.group(1).strip()
        for m in re.finditer(r"<LINEERROR>(.*?)</LINEERROR>", xml_text, re.IGNORECASE | re.DOTALL)
    ]
    return r


async def post_xml(client: httpx.AsyncClient, xml: str) -> str:
    resp = await client.post(
        BASE_URL,
        content=xml,
        headers={"Content-Type": "text/xml; charset=utf-8"},
    )
    resp.raise_for_status()
    return resp.text


async def run_one(client: httpx.AsyncClient, date: str) -> dict:
    create_xml = build_create_xml(date)
    create_raw = await post_xml(client, create_xml)
    cr = parse_response(create_raw)

    row = {
        "date": date,
        "created": cr.created,
        "errors": cr.errors,
        "exceptions": cr.exceptions,
        "last_vch_id": cr.last_vch_id,
        "line_errors": cr.line_errors,
        "deleted": None,
        "delete_errors": None,
        "delete_exceptions": None,
        "delete_line_errors": None,
    }

    if cr.created == 1 and cr.last_vch_id:
        del_xml = build_delete_xml(date, cr.last_vch_id)
        del_raw = await post_xml(client, del_xml)
        dr = parse_response(del_raw)
        row["deleted"] = dr.deleted
        row["delete_errors"] = dr.errors
        row["delete_exceptions"] = dr.exceptions
        row["delete_line_errors"] = dr.line_errors

    return row


def format_row(row: dict) -> str:
    status = "CREATED" if row["created"] == 1 else "FAILED"
    le = "; ".join(row["line_errors"]) if row["line_errors"] else ""
    del_part = ""
    if row["deleted"] is not None:
        if row["deleted"] == 1:
            del_part = " | DELETED=1"
        else:
            dle = "; ".join(row["delete_line_errors"] or [])
            del_part = (
                f" | DELETE FAILED err={row['delete_errors']} exc={row['delete_exceptions']} {dle}"
            )
    return (
        f"{row['date']}  {status:<7}  "
        f"err={row['errors']}  exc={row['exceptions']}  "
        f"LASTVCHID={row['last_vch_id']}  LINEERROR={le!r}{del_part}"
    )


async def main() -> None:
    print(f"Tally: {BASE_URL}")
    print(f"Company: {COMPANY}")
    print(f"Debit ledger: {EXPENSE_LEDGER!r}  |  Credit ledger: {CASH_LEDGER!r}")
    print(f"Test dates: {TEST_DATES}")
    print("-" * 100)

    results: list[dict] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for date in TEST_DATES:
            print(f"\n>>> Attempting DATE={date} ...", flush=True)
            try:
                row = await run_one(client, date)
            except Exception as e:  # pragma: no cover
                row = {
                    "date": date,
                    "created": 0,
                    "errors": -1,
                    "exceptions": -1,
                    "last_vch_id": None,
                    "line_errors": [f"EXCEPTION: {type(e).__name__}: {e}"],
                    "deleted": None,
                    "delete_errors": None,
                    "delete_exceptions": None,
                    "delete_line_errors": None,
                }
            results.append(row)
            print("    " + format_row(row))

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    for row in results:
        print(format_row(row))


if __name__ == "__main__":
    asyncio.run(main())
