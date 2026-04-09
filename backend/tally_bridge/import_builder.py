"""Build Tally IMPORTDATA XML payloads for creating/cancelling/deleting vouchers, ledgers, groups.

All functions are pure — no I/O, no side effects. Each returns an XML string.
Tally import date format: YYYYMMDD (different from query format DD-MM-YYYY).

CRITICAL (from live Tally exploration — docs/tally-write-exploration.md):
- NAME.LIST is REQUIRED for all master operations (create AND delete). Without it, Tally crashes.
- Voucher delete/cancel uses TAGNAME="Master ID" + TAGVALUE=LASTVCHID (not VCHKEY).
- PERSISTEDVIEW is required for Sales/Purchase vouchers.
"""
from typing import Literal
from xml.sax.saxutils import escape as xml_escape


def _esc(s: str) -> str:
    """Escape XML special characters in user-provided strings.

    Includes attribute escaping (`"` and `'`) so the same helper works
    for both element text and attribute values.
    """
    return xml_escape(s, {'"': "&quot;", "'": "&apos;"})


def _require(value: str, name: str) -> str:
    """Validate that a required string parameter is non-empty after stripping."""
    if not value or not value.strip():
        raise ValueError(f"{name} is required")
    return value


def _wrap_import(report_name: Literal["Vouchers", "All Masters"], company: str, inner_xml: str) -> str:
    """Wrap entity XML in the standard IMPORTDATA envelope."""
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>{report_name}</REPORTNAME>
<STATICVARIABLES><SVCURRENTCOMPANY>{_esc(company)}</SVCURRENTCOMPANY></STATICVARIABLES>
</REQUESTDESC>
<REQUESTDATA>
<TALLYMESSAGE xmlns:UDF="TallyUDF">
{inner_xml}
</TALLYMESSAGE>
</REQUESTDATA>
</IMPORTDATA></BODY></ENVELOPE>"""


def build_create_payment_voucher(
    date: str,
    debit_ledger: str,
    credit_ledger: str,
    amount: float,
    narration: str,
    company: str,
    gst_entries: list[dict] | None = None,
) -> str:
    """Build XML to create a Payment voucher in Tally.

    Args:
        date: YYYYMMDD format.
        debit_ledger: Expense ledger name (e.g., "Travel Expenses").
        credit_ledger: Cash/Bank ledger name (e.g., "Cash").
        amount: Total payment amount (positive number).
        narration: Description of the expense.
        company: Tally company name.
        gst_entries: Optional list of {"ledger": str, "amount": float} for GST components.
    """
    if amount <= 0:
        raise ValueError(f"amount must be positive, got {amount}")
    gst_total = sum(e["amount"] for e in (gst_entries or []))
    if gst_total < 0 or gst_total > amount:
        raise ValueError(f"invalid gst total {gst_total} for amount {amount}")

    _require(date, "date")
    _require(debit_ledger, "debit_ledger")
    _require(credit_ledger, "credit_ledger")
    _require(narration, "narration")
    _require(company, "company")

    base_amount = amount - gst_total

    entries = []
    entries.append(
        f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(debit_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-{base_amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
    )
    for gst in gst_entries or []:
        entries.append(
            f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(gst["ledger"])}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-{gst["amount"]:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
        )
    entries.append(
        f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{_esc(credit_ledger)}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
    )

    entries_xml = "\n".join(entries)
    voucher_xml = f"""<VOUCHER VCHTYPE="Payment" ACTION="Create">
<DATE>{_esc(date)}</DATE>
<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
<NARRATION>{_esc(narration)}</NARRATION>
<PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
{entries_xml}
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_create_ledger(
    name: str,
    parent: str,
    company: str,
    gstin: str | None = None,
) -> str:
    """Build XML to create a ledger master in Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.
    """
    _require(name, "name")
    _require(parent, "parent")
    _require(company, "company")

    gstin_xml = f"\n<PARTYGSTIN>{_esc(gstin)}</PARTYGSTIN>" if gstin else ""
    ledger_xml = f"""<LEDGER NAME="{_esc(name)}" ACTION="Create">
<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST>
<PARENT>{_esc(parent)}</PARENT>{gstin_xml}
</LEDGER>"""
    return _wrap_import("All Masters", company, ledger_xml)


def build_create_group(name: str, parent: str, company: str) -> str:
    """Build XML to create an account group in Tally."""
    _require(name, "name")
    _require(parent, "parent")
    _require(company, "company")

    group_xml = f"""<GROUP NAME="{_esc(name)}" ACTION="Create">
<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST>
<PARENT>{_esc(parent)}</PARENT>
</GROUP>"""
    return _wrap_import("All Masters", company, group_xml)


def build_delete_voucher(
    voucher_type: str,
    master_id: str,
    date: str,
    company: str,
) -> str:
    """Build XML to delete a voucher from Tally.

    Uses TAGNAME="Master ID" + TAGVALUE (the LASTVCHID from creation response).
    """
    _require(voucher_type, "voucher_type")
    _require(master_id, "master_id")
    _require(date, "date")
    _require(company, "company")

    voucher_xml = f"""<VOUCHER DATE="{_esc(date)}" TAGNAME="Master ID" TAGVALUE="{_esc(master_id)}" VCHTYPE="{_esc(voucher_type)}" ACTION="Delete">
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_cancel_voucher(
    voucher_type: str,
    master_id: str,
    date: str,
    company: str,
    narration: str = "",
) -> str:
    """Build XML to cancel a voucher in Tally (preserves audit trail).

    Cancel returns ALTERED=1 from Tally (cancel is internally an alter).
    Preferred over delete for undo operations.
    """
    _require(voucher_type, "voucher_type")
    _require(master_id, "master_id")
    _require(date, "date")
    _require(company, "company")

    narration_xml = f"\n<NARRATION>{_esc(narration)}</NARRATION>" if narration else ""
    voucher_xml = f"""<VOUCHER DATE="{_esc(date)}" TAGNAME="Master ID" TAGVALUE="{_esc(master_id)}" VCHTYPE="{_esc(voucher_type)}" ACTION="Cancel">{narration_xml}
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_delete_ledger(name: str, company: str) -> str:
    """Build XML to delete a ledger master from Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.
    """
    _require(name, "name")
    _require(company, "company")

    ledger_xml = f"""<LEDGER NAME="{_esc(name)}" ACTION="Delete">
<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST>
</LEDGER>"""
    return _wrap_import("All Masters", company, ledger_xml)


def build_delete_group(name: str, company: str) -> str:
    """Build XML to delete an account group from Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.
    """
    _require(name, "name")
    _require(company, "company")

    group_xml = f"""<GROUP NAME="{_esc(name)}" ACTION="Delete">
<NAME.LIST><NAME>{_esc(name)}</NAME></NAME.LIST>
</GROUP>"""
    return _wrap_import("All Masters", company, group_xml)
