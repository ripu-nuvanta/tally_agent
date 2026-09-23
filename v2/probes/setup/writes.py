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
from v2.probes.reads import TB_EXPLODE_VARS, voucher_request
from v2.probes.safety import check_request
from v2.probes.setup.import_xml import ImportResult, esc, wrap_import

READBACK_FROM, READBACK_TO = "01-04-2025", "31-03-2026"
B_READBACK_FROM, B_READBACK_TO = "01-04-2022", "31-03-2026"   # company B's date window (S0-B spec §4)
POPUP_STOCK_GROUP = "Electronics"    # exists in the seed company; a duplicate create raises the blocking modal
VOUCHER_FIELDS = ["MasterId", "Narration", "Date", "IsPostDated"]
LEDGER_FIELDS = ["Name", "Parent", "Email", "AlterID"]
GROUP_FIELDS = ["Name", "Parent"]
UNIT_FIELDS = ["Name", "BaseUnits", "Conversion"]
ITEM_FIELDS = ["Name", "BaseUnits", "Parent"]
VOUCHER_TYPE_FIELDS = ["Name", "Parent"]


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
            if post_dated:
                self.say(f"post-dated voucher created (LASTVCHID {result.last_vch_id}) but not listed in the Voucher "
                         "collection")
                return result.last_vch_id
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

    # --- vouchers (company B) ---------------------------------------------------------------------------------------
    def create_b_voucher(self, company: str, *, vch_type: str, date: str, narration: str, party: str,
                         lines: list[tuple[str, Decimal, bool]],
                         inventory: list[tuple[str, str, Decimal, Decimal, Decimal]] = (),
                         bills: list[tuple[str, str, Decimal, str | None]] = (),
                         optional: bool = False) -> str:
        """Sales/Purchase (with stock + GST), Receipt/Payment/Journal — the caller owns the sign convention (docs

        Op 6/7/8; live 2026-09-22): AMOUNT is signed as given per line, ISDEEMEDPOSITIVE is passed as given, and this
        method's own balance check is the only thing that proves the two agree. Nothing is sent to Tally until the
        voucher is proven to balance. `BILLALLOCATIONS.LIST` nests only under the line whose ledger equals `party`.
        `ISCANCELLED` is never written here (cancelling is not reliably settable on import — Task 6 pause step).

        **Ordering contract for `lines` when `inventory` is non-empty:** the party line first, then the nominal
        Sales/Purchase ledger, then any GST lines — `ACCOUNTINGALLOCATIONS.LIST` on every inventory row points at
        the first non-party line, so a caller that puts a GST line there instead would silently misallocate goods
        to a tax ledger. Enforced only to the extent that `lines` must have at least 2 entries when `inventory` is
        given (`len(lines) >= 2`); the specific ordering itself cannot be checked at this layer (ledger names carry
        no semantic tag) and is the caller's (Task 6's) responsibility.

        **`is_invoice_type` limitation:** invoice mode is decided from the voucher type NAME (`Sales`, `Purchase`,
        or a name starting with either, e.g. `"Sales - GST"` / `"Purchase - GST"`) — this layer has no voucher-type
        collection to look up a type's PARENT. A custom type whose name does not start with Sales/Purchase while
        its parent does (e.g. `"Export Invoice"` parented to `Sales`) will be misclassified as non-invoice and
        emit `ALLLEDGERENTRIES.LIST` + `Accounting Voucher View`, which Tally will likely answer with
        `EXCEPTIONS=1`. Callers naming such a type must alias it to start with `Sales`/`Purchase`.
        """
        check_writable(company)
        total = sum((amount for _, amount, _ in lines), Decimal("0.00"))
        if total != Decimal("0.00"):
            raise ValueError(f"Voucher {narration!r} does not balance: {total}")

        # Op 6/7 (docs/tally-write-exploration-v4.md) — confirmed 2026-09-23 by backend/tally_bridge/import_builder.py,
        # the production writer that has actually landed invoices in live Tally: stock+GST Sales/Purchase are
        # live-verified only under unprefixed LEDGERENTRIES.LIST + Invoice Voucher View + ISINVOICE=Yes +
        # ISPARTYLEDGER=Yes on the party line. ALLLEDGERENTRIES.LIST + Accounting Voucher View (used here for
        # Receipt/Payment/Journal/Contra, matching create_payment/Op 8/9) is reserved for the non-invoice path.
        # Defined once and reused by the inventory-placement guard below so the two checks cannot drift apart again.
        is_invoice_type = (vch_type in ("Sales", "Purchase")
                           or vch_type.startswith("Sales") or vch_type.startswith("Purchase"))
        ledger_tag = "LEDGERENTRIES.LIST" if is_invoice_type else "ALLLEDGERENTRIES.LIST"

        if inventory and not is_invoice_type:
            raise ValueError("Inventory lines belong on Sales/Purchase only")
        if inventory and len(lines) < 2:
            raise ValueError("Inventory lines need a party line and a nominal ledger line in `lines`")

        ledger_blocks = []
        for ledger, amount, deemed_positive in lines:
            bill_xml = ""
            if ledger == party and bills:
                bill_xml = "".join(
                    f"\n    <BILLALLOCATIONS.LIST>\n      <NAME>{esc(name)}</NAME>\n      "
                    f"<BILLTYPE>{esc(bill_type)}</BILLTYPE>\n      <AMOUNT>{bill_amount:.2f}</AMOUNT>"
                    + (f"\n      <BILLCREDITPERIOD>{esc(credit_period)}</BILLCREDITPERIOD>" if credit_period else "")
                    + "\n    </BILLALLOCATIONS.LIST>"
                    for name, bill_type, bill_amount, credit_period in bills)
            party_flag = ("\n    <ISPARTYLEDGER>Yes</ISPARTYLEDGER>" if is_invoice_type and ledger == party else "")
            ledger_blocks.append(
                f"""  <{ledger_tag}>
    <LEDGERNAME>{esc(ledger)}</LEDGERNAME>
    <ISDEEMEDPOSITIVE>{"Yes" if deemed_positive else "No"}</ISDEEMEDPOSITIVE>
    <AMOUNT>{amount:.2f}</AMOUNT>{party_flag}{bill_xml}
  </{ledger_tag}>""")

        # The nominal (goods) ledger for every inventory row's ACCOUNTINGALLOCATIONS.LIST: the first line that isn't
        # the party line. `lines` is expected to list party first, then the nominal Sales/Purchase ledger, then any
        # GST lines (matches Op 6/7 and both this method's callers' test fixtures) — Task 6 must keep that ordering.
        inventory_deemed_positive = "Yes" if vch_type == "Purchase" else "No"
        nominal_ledger = next((ledger for ledger, _, _ in lines if ledger != party), party)
        inventory_blocks = []
        for item, unit, qty, rate, amount in inventory:
            qty_unit = f"{qty} {esc(unit)}"
            inventory_blocks.append(
                f"""  <ALLINVENTORYENTRIES.LIST>
    <STOCKITEMNAME>{esc(item)}</STOCKITEMNAME>
    <ISDEEMEDPOSITIVE>{inventory_deemed_positive}</ISDEEMEDPOSITIVE>
    <RATE>{rate:.2f}/{esc(unit)}</RATE>
    <AMOUNT>{amount:.2f}</AMOUNT>
    <ACTUALQTY>{qty_unit}</ACTUALQTY>
    <BILLEDQTY>{qty_unit}</BILLEDQTY>
    <ACCOUNTINGALLOCATIONS.LIST>
      <LEDGERNAME>{esc(nominal_ledger)}</LEDGERNAME>
      <ISDEEMEDPOSITIVE>{inventory_deemed_positive}</ISDEEMEDPOSITIVE>
      <AMOUNT>{amount:.2f}</AMOUNT>
    </ACCOUNTINGALLOCATIONS.LIST>
  </ALLINVENTORYENTRIES.LIST>""")

        optional_xml = "\n  <ISOPTIONAL>Yes</ISOPTIONAL>" if optional else ""
        if is_invoice_type:
            header = (f'<VOUCHER VCHTYPE="{esc(vch_type)}" ACTION="Create">\n'
                      f"  <DATE>{date}</DATE>\n  <NARRATION>{esc(narration)}</NARRATION>\n"
                      f"  <VOUCHERTYPENAME>{esc(vch_type)}</VOUCHERTYPENAME>\n"
                      f"  <PARTYLEDGERNAME>{esc(party)}</PARTYLEDGERNAME>\n"
                      f"  <PARTYNAME>{esc(party)}</PARTYNAME>\n"
                      f"  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>\n"
                      f"  <ISINVOICE>Yes</ISINVOICE>\n"
                      f"  <EFFECTIVEDATE>{date}</EFFECTIVEDATE>{optional_xml}")
        else:
            header = (f'<VOUCHER VCHTYPE="{esc(vch_type)}" ACTION="Create">\n'
                      f"  <DATE>{date}</DATE>\n  <NARRATION>{esc(narration)}</NARRATION>\n"
                      f"  <VOUCHERTYPENAME>{esc(vch_type)}</VOUCHERTYPENAME>\n"
                      f"  <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>{optional_xml}")
        inner = f"""{header}
{chr(10).join(ledger_blocks)}
{chr(10).join(inventory_blocks)}
</VOUCHER>"""
        result = self.import_("Vouchers", company, inner)
        if result.created != 1 or not result.clean or result.last_vch_id in ("", "0"):
            raise WriteFailed(f"Voucher {narration!r} not created: {result}")
        return result.last_vch_id

    def voucher_by_tag(self, company: str, tag: int) -> dict[str, str] | None:
        """The B voucher whose narration starts `[S0-B:{tag}]`, over B's own date window (S0-B spec §4)."""
        xml = voucher_request("S0BVouchers", VOUCHER_FIELDS, company, from_date=B_READBACK_FROM, to_date=B_READBACK_TO)
        return next((v for v in read_objects(self.post(xml), "VOUCHER", VOUCHER_FIELDS)
                    if v.get("Narration", "").startswith(f"[S0-B:{tag}]")), None)

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

    # --- masters (company B) -----------------------------------------------------------------------------------------
    def list_groups(self, company: str) -> dict[str, str]:
        xml = wrap_collection("S0BGroups", "Group", GROUP_FIELDS, company)
        return {row["Name"]: row.get("Parent", "") for row in read_objects(self.post(xml), "GROUP", GROUP_FIELDS)}

    def list_units(self, company: str) -> list[str]:
        xml = wrap_collection("S0BUnits", "Unit", UNIT_FIELDS, company)
        return [row["Name"] for row in read_objects(self.post(xml), "UNIT", UNIT_FIELDS)]

    def list_stock_items(self, company: str) -> dict[str, str]:
        xml = wrap_collection("S0BItems", "StockItem", ITEM_FIELDS, company)
        return {row["Name"]: row.get("BaseUnits", "")
                for row in read_objects(self.post(xml), "STOCKITEM", ITEM_FIELDS)}

    def list_ledgers(self, company: str) -> dict[str, str]:
        xml = wrap_collection("S0BLedgers", "Ledger", LEDGER_FIELDS, company)
        return {row["Name"]: row.get("Parent", "") for row in read_objects(self.post(xml), "LEDGER", LEDGER_FIELDS)}

    def list_voucher_types(self, company: str) -> list[str]:
        xml = wrap_collection("S0BVoucherTypes", "VoucherType", VOUCHER_TYPE_FIELDS, company)
        return [row["Name"] for row in read_objects(self.post(xml), "VOUCHERTYPE", VOUCHER_TYPE_FIELDS)]

    def b_trial_balance(self, company: str, from_date: str, to_date: str) -> str:
        """An exploded (EXPLODEFLAG=Yes, probe 17) Trial Balance — company_b.py's `_verify` compares
        primary/second-level group totals only from this; ledger-level TB shape is deferred to probes 16/17
        (S0-D7: a probe never guesses a request another probe must confirm)."""
        return self.post(wrap_report("Trial Balance", from_date, to_date, company, extra_vars=TB_EXPLODE_VARS),
                         timeout=60.0)

    def b_bills_receivable(self, company: str, as_on: str) -> str:
        return self.post(wrap_report("Bills Receivable", as_on, as_on, company), timeout=60.0)

    def create_group(self, company: str, name: str, parent: str) -> None:
        check_writable(company)
        if name in self.list_groups(company):
            self.say(f"{name} already exists — not re-created")
            return
        inner = (f'<GROUP NAME="{esc(name)}" ACTION="Create">\n  <NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST>\n'
                 f'  <PARENT>{esc(parent)}</PARENT>\n</GROUP>')
        result = self.import_("All Masters", company, inner)
        if not ((result.created == 1 or result.altered == 1) and result.clean):
            raise WriteFailed(f"Group {name!r} not created: {result}")
        if name not in self.list_groups(company):
            raise WriteFailed(f"Group {name!r} not found on read-back")

    def create_unit(self, company: str, name: str, *, base: str | None = None, conversion: int | None = None) -> None:
        check_writable(company)
        if name in self.list_units(company):
            self.say(f"{name} already exists — not re-created")
            return
        compound = ("\n  <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>" if base is None else
                    f"\n  <BASEUNITS>{esc(base)}</BASEUNITS>\n  <ADDITIONALUNITS>{esc(base)}</ADDITIONALUNITS>"
                    f"\n  <CONVERSION>{conversion}</CONVERSION>\n  <ISSIMPLEUNIT>No</ISSIMPLEUNIT>")
        inner = f'<UNIT ACTION="Create">\n  <NAME>{esc(name)}</NAME>{compound}\n</UNIT>'
        result = self.import_("All Masters", company, inner)
        if not ((result.created == 1 or result.altered == 1) and result.clean):
            raise WriteFailed(f"Unit {name!r} not created: {result}")
        if name not in self.list_units(company):
            raise WriteFailed(f"Unit {name!r} not found on read-back")

    def create_stock_item(self, company: str, name: str, *, unit: str, hsn: str | None = None,
                          opening_qty: Decimal | None = None, opening_rate: Decimal | None = None) -> None:
        check_writable(company)
        if name in self.list_stock_items(company):
            self.say(f"{name} already exists — not re-created")
            return
        gst = (f"\n  <GSTAPPLICABLE>Applicable</GSTAPPLICABLE>\n  <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>"
               f"\n  <HSNCODE>{esc(hsn)}</HSNCODE>\n  <HSN>{esc(hsn)}</HSN>\n  "
               f"<HSNDETAILS.LIST><HSNCODE>{esc(hsn)}</HSNCODE></HSNDETAILS.LIST>"
               if hsn else "\n  <GSTAPPLICABLE>Not Applicable</GSTAPPLICABLE>")
        opening = ("" if opening_qty is None else
                   f"\n  <OPENINGBALANCE>{opening_qty} {esc(unit)}</OPENINGBALANCE>"
                   f"\n  <OPENINGRATE>{opening_rate:.2f}/{esc(unit)}</OPENINGRATE>"
                   f"\n  <OPENINGVALUE>{(opening_qty * opening_rate):.2f}</OPENINGVALUE>")
        inner = (f'<STOCKITEM NAME="{esc(name)}" ACTION="Create">\n  <NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST>\n'
                 f'  <BASEUNITS>{esc(unit)}</BASEUNITS>{gst}{opening}\n</STOCKITEM>')
        result = self.import_("All Masters", company, inner)
        if not ((result.created == 1 or result.altered == 1) and result.clean):
            raise WriteFailed(f"Stock item {name!r} not created: {result}")
        if name not in self.list_stock_items(company):
            raise WriteFailed(f"Stock item {name!r} not found on read-back")

    def create_party_ledger(self, company: str, name: str, *, parent: str, bill_wise: bool,
                            opening: Decimal | None = None, gstin: str | None = None) -> None:
        check_writable(company)
        if self.ledger(company, name) is not None:
            self.say(f"{name} already exists — not re-created")
            return
        extra = "".join(filter(None, [
            f"\n  <OPENINGBALANCE>{opening:.2f}</OPENINGBALANCE>" if opening is not None else "",
            f"\n  <PARTYGSTIN>{esc(gstin)}</PARTYGSTIN>\n  <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>" if gstin
            else "\n  <GSTREGISTRATIONTYPE>Unregistered</GSTREGISTRATIONTYPE>",
        ]))
        inner = (f'<LEDGER NAME="{esc(name)}" ACTION="Create">\n  <NAME.LIST><NAME>{esc(name)}</NAME></NAME.LIST>\n'
                 f'  <PARENT>{esc(parent)}</PARENT>\n  <ISBILLWISEON>{"Yes" if bill_wise else "No"}</ISBILLWISEON>'
                 f'\n  <LEDSTATENAME>Maharashtra</LEDSTATENAME>{extra}\n</LEDGER>')
        result = self.import_("All Masters", company, inner)
        if not ((result.created == 1 or result.altered == 1) and result.clean):
            raise WriteFailed(f"Party ledger {name!r} not created: {result}")
        row = self.ledger(company, name)
        if row is None or row["Parent"] != parent:
            raise WriteFailed(f"Party ledger {name!r} not found under {parent!r} on read-back")

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
