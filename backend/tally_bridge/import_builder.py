"""Build Tally IMPORTDATA XML payloads for creating/cancelling/deleting vouchers, ledgers, groups.

All functions are pure — no I/O, no side effects. Each returns an XML string.
Tally import date format: YYYYMMDD (different from query format DD-MM-YYYY).

CRITICAL (from live Tally exploration — docs/tally-write-exploration.md):
- NAME.LIST is REQUIRED for all master operations (create AND delete). Without it, Tally crashes.
- Voucher delete/cancel uses TAGNAME="Master ID" + TAGVALUE=LASTVCHID (not VCHKEY).
- PERSISTEDVIEW is required for Sales/Purchase vouchers.
"""


def _wrap_import(report_name: str, company: str, inner_xml: str) -> str:
    """Wrap entity XML in the standard IMPORTDATA envelope."""
    return f"""<ENVELOPE>
<HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
<BODY><IMPORTDATA>
<REQUESTDESC>
<REPORTNAME>{report_name}</REPORTNAME>
<STATICVARIABLES><SVCURRENTCOMPANY>{company}</SVCURRENTCOMPANY></STATICVARIABLES>
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
    gst_total = sum(e["amount"] for e in (gst_entries or []))
    base_amount = amount - gst_total

    entries = []
    entries.append(
        f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{debit_ledger}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-{base_amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
    )
    for gst in gst_entries or []:
        entries.append(
            f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{gst["ledger"]}</LEDGERNAME>
<ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
<AMOUNT>-{gst["amount"]:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
        )
    entries.append(
        f"""<ALLLEDGERENTRIES.LIST>
<LEDGERNAME>{credit_ledger}</LEDGERNAME>
<ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
<AMOUNT>{amount:.2f}</AMOUNT>
</ALLLEDGERENTRIES.LIST>"""
    )

    entries_xml = "\n".join(entries)
    voucher_xml = f"""<VOUCHER VCHTYPE="Payment" ACTION="Create">
<DATE>{date}</DATE>
<VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
<NARRATION>{narration}</NARRATION>
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
    gstin_xml = f"\n<PARTYGSTIN>{gstin}</PARTYGSTIN>" if gstin else ""
    ledger_xml = f"""<LEDGER NAME="{name}" ACTION="Create">
<NAME.LIST><NAME>{name}</NAME></NAME.LIST>
<PARENT>{parent}</PARENT>{gstin_xml}
</LEDGER>"""
    return _wrap_import("All Masters", company, ledger_xml)


def build_create_group(name: str, parent: str, company: str) -> str:
    """Build XML to create an account group in Tally."""
    group_xml = f"""<GROUP NAME="{name}" ACTION="Create">
<NAME.LIST><NAME>{name}</NAME></NAME.LIST>
<PARENT>{parent}</PARENT>
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
    voucher_xml = f"""<VOUCHER DATE="{date}" TAGNAME="Master ID" TAGVALUE="{master_id}" VCHTYPE="{voucher_type}" ACTION="Delete">
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
    narration_xml = f"\n<NARRATION>{narration}</NARRATION>" if narration else ""
    voucher_xml = f"""<VOUCHER DATE="{date}" TAGNAME="Master ID" TAGVALUE="{master_id}" VCHTYPE="{voucher_type}" ACTION="Cancel">{narration_xml}
</VOUCHER>"""
    return _wrap_import("Vouchers", company, voucher_xml)


def build_delete_ledger(name: str, company: str) -> str:
    """Build XML to delete a ledger master from Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.
    """
    ledger_xml = f"""<LEDGER NAME="{name}" ACTION="Delete">
<NAME.LIST><NAME>{name}</NAME></NAME.LIST>
</LEDGER>"""
    return _wrap_import("All Masters", company, ledger_xml)


def build_delete_group(name: str, company: str) -> str:
    """Build XML to delete an account group from Tally.

    CRITICAL: NAME.LIST is required — without it Tally crashes with memory violation.
    """
    group_xml = f"""<GROUP NAME="{name}" ACTION="Delete">
<NAME.LIST><NAME>{name}</NAME></NAME.LIST>
</GROUP>"""
    return _wrap_import("All Masters", company, group_xml)
