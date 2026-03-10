"""
Parse TallyPrime XML responses into normalized Python dicts.
Handles Tally's inconsistent casing, empty tags, comma-formatted amounts.
"""
import re
import xml.etree.ElementTree as ET
from datetime import datetime


def sanitize_xml(raw_xml: str) -> str:
    """Remove invalid XML character references that TallyPrime sometimes emits.

    Tally uses control characters like &#4; (EOT) as field separators in
    some responses. These are not valid XML and cause ET.ParseError.
    """
    return re.sub(r"&#([0-8]|1[0-1]|1[4-9]|2[0-9]|3[0-1]);", "", raw_xml)


def parse_amount(text: str | None) -> float:
    if not text or not text.strip():
        return 0.0
    cleaned = text.strip().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


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


def _get_text(element: ET.Element, tag: str) -> str:
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return ""


def parse_trial_balance(raw_xml: str) -> list[dict]:
    """Parse Trial Balance report from Tally's TYPE=Data XML.

    Real Tally structure uses alternating sibling pairs:
      DSPACCNAME (contains DSPDISPNAME) followed by
      DSPACCINFO (contains DSPCLDRAMT>DSPCLDRAMTA and DSPCLCRAMT>DSPCLCRAMTA)
    """
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows = []
    # Iterate direct children of root, pairing DSPACCNAME with following DSPACCINFO
    children = list(root)
    current_name = None
    for child in children:
        if child.tag == "DSPACCNAME":
            current_name = _get_text(child, "DSPDISPNAME")
        elif child.tag == "DSPACCINFO" and current_name:
            # Debit: DSPCLDRAMT > DSPCLDRAMTA
            debit_el = child.find("DSPCLDRAMT")
            debit = 0.0
            if debit_el is not None:
                debit = parse_amount(_get_text(debit_el, "DSPCLDRAMTA"))
            # Credit: DSPCLCRAMT > DSPCLCRAMTA
            credit_el = child.find("DSPCLCRAMT")
            credit = 0.0
            if credit_el is not None:
                credit = parse_amount(_get_text(credit_el, "DSPCLCRAMTA"))
            rows.append({
                "account_name": current_name,
                "debit_amount": debit,
                "credit_amount": credit,
                "closing_balance": debit + credit,
            })
            current_name = None
    return rows


def parse_ledger_list(raw_xml: str) -> list[dict]:
    root = ET.fromstring(sanitize_xml(raw_xml))
    ledgers = []
    for ledger in root.iter("LEDGER"):
        name = _get_text(ledger, "NAME") or ledger.get("NAME", "")
        if not name:
            continue
        ledgers.append({
            "name": name,
            "parent_group": _get_text(ledger, "PARENT"),
            "closing_balance": parse_amount(_get_text(ledger, "CLOSINGBALANCE")),
            "opening_balance": parse_amount(_get_text(ledger, "OPENINGBALANCE")),
        })
    return ledgers


def parse_profit_and_loss(raw_xml: str) -> list[dict]:
    """Parse Profit & Loss report from Tally's TYPE=Data XML.

    Real Tally structure uses alternating sibling pairs:
      DSPACCNAME (contains DSPDISPNAME) followed by
      PLAMT (contains BSMAINAMT for main amounts, PLSUBAMT for sub-items)
    Amount: prefer BSMAINAMT, fall back to PLSUBAMT.
    Sign convention: negative = debit (expense), positive = credit (income).
    """
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows = []
    children = list(root)
    current_name = None
    for child in children:
        if child.tag == "DSPACCNAME":
            current_name = _get_text(child, "DSPDISPNAME")
        elif child.tag == "PLAMT" and current_name:
            main_amt = parse_amount(_get_text(child, "BSMAINAMT"))
            sub_amt = parse_amount(_get_text(child, "PLSUBAMT"))
            amount = main_amt if main_amt != 0.0 else sub_amt
            debit = amount if amount < 0 else 0.0
            credit = amount if amount > 0 else 0.0
            rows.append({
                "account_name": current_name,
                "debit_amount": debit,
                "credit_amount": credit,
                "closing_balance": amount,
            })
            current_name = None
    return rows


def parse_balance_sheet(raw_xml: str) -> list[dict]:
    """Parse Balance Sheet report from Tally's TYPE=Data XML.

    Real Tally structure uses alternating sibling pairs:
      BSNAME (contains DSPACCNAME > DSPDISPNAME) followed by
      BSAMT (contains BSMAINAMT for main amounts, BSSUBAMT for sub-items)
    Sign convention: negative = debit (asset), positive = credit (liability/equity).
    """
    root = ET.fromstring(sanitize_xml(raw_xml))
    rows = []
    children = list(root)
    current_name = None
    for child in children:
        if child.tag == "BSNAME":
            name_el = child.find(".//DSPDISPNAME")
            if name_el is not None and name_el.text:
                current_name = name_el.text.strip()
        elif child.tag == "BSAMT" and current_name:
            main_amt = parse_amount(_get_text(child, "BSMAINAMT"))
            sub_amt = parse_amount(_get_text(child, "BSSUBAMT"))
            amount = main_amt if main_amt != 0.0 else sub_amt
            debit = amount if amount < 0 else 0.0
            credit = amount if amount > 0 else 0.0
            rows.append({
                "account_name": current_name,
                "debit_amount": debit,
                "credit_amount": credit,
                "closing_balance": amount,
            })
            current_name = None
    return rows


def parse_bills(raw_xml: str) -> list[dict]:
    root = ET.fromstring(sanitize_xml(raw_xml))
    bills = []
    # Tally returns BILLFIXED (not BILLSFIXED) with sibling BILLCL/BILLDUE/BILLOVERDUE.
    # We iterate all children and pair BILLFIXED with the BILLCL that follows it.
    elements = list(root.iter())
    i = 0
    while i < len(elements):
        el = elements[i]
        if el.tag == "BILLFIXED":
            bill_ref = _get_text(el, "BILLREF")
            if not bill_ref:
                i += 1
                continue
            party = _get_text(el, "BILLPARTY")
            bill_date = _get_text(el, "BILLDATE")
            # Look for sibling BILLCL after this BILLFIXED
            amount = 0.0
            due_date = ""
            overdue_days = ""
            for j in range(i + 1, min(i + 10, len(elements))):
                sib = elements[j]
                if sib.tag == "BILLFIXED":
                    break
                if sib.tag == "BILLCL" and sib.text:
                    amount = abs(parse_amount(sib.text))
                elif sib.tag == "BILLDUE" and sib.text:
                    due_date = sib.text.strip()
                elif sib.tag == "BILLOVERDUE" and sib.text:
                    overdue_days = sib.text.strip()
            bills.append({
                "bill_number": bill_ref,
                "party_name": party,
                "bill_date": bill_date,
                "amount": amount,
                "pending_amount": amount,
                "due_date": due_date,
                "overdue_days": overdue_days,
            })
        i += 1
    return bills


def parse_stock_summary(raw_xml: str) -> list[dict]:
    """Parse Stock Summary report from Tally's TYPE=Data XML.

    Real Tally structure uses alternating sibling pairs:
      DSPACCNAME (contains DSPDISPNAME) followed by
      DSPSTKINFO (contains DSPSTKCL with DSPCLQTY, DSPCLRATE, DSPCLAMTA)

    DSPCLQTY format: "-2.0000 NOS" (number + space + unit).
    No parent group info in TYPE=Data reports.
    """
    root = ET.fromstring(sanitize_xml(raw_xml))
    items = []
    children = list(root)
    current_name = None
    for child in children:
        if child.tag == "DSPACCNAME":
            current_name = _get_text(child, "DSPDISPNAME")
        elif child.tag == "DSPSTKINFO" and current_name:
            stk_cl = child.find("DSPSTKCL")
            qty = 0.0
            unit = ""
            rate = 0.0
            value = 0.0
            if stk_cl is not None:
                qty_text = _get_text(stk_cl, "DSPCLQTY")
                if qty_text:
                    parts = qty_text.split()
                    if parts:
                        try:
                            qty = float(parts[0].replace(",", ""))
                        except ValueError:
                            pass
                        if len(parts) > 1:
                            unit = " ".join(parts[1:])
                rate = parse_amount(_get_text(stk_cl, "DSPCLRATE"))
                value = parse_amount(_get_text(stk_cl, "DSPCLAMTA"))
            items.append({
                "name": current_name,
                "parent_group": "",
                "base_units": unit,
                "closing_quantity": qty,
                "closing_rate": rate,
                "closing_value": value,
            })
            current_name = None
    return items


def _filter_vouchers_by_date(vouchers: list[dict], from_date: str, to_date: str) -> list[dict]:
    """Filter vouchers by date range (DD-MM-YYYY format). Safety net for TDL filter."""
    try:
        dt_from = datetime.strptime(from_date, "%d-%m-%Y")
        dt_to = datetime.strptime(to_date, "%d-%m-%Y")
    except ValueError:
        return vouchers
    filtered = []
    for v in vouchers:
        date_str = v.get("date", "")
        if not date_str:
            continue
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
            if dt_from <= dt <= dt_to:
                filtered.append(v)
        except ValueError:
            filtered.append(v)
    return filtered


def parse_vouchers(raw_xml: str, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
    root = ET.fromstring(sanitize_xml(raw_xml))
    vouchers = []
    for v in root.iter("VOUCHER"):
        date_str = _get_text(v, "DATE")
        voucher_type = _get_text(v, "VOUCHERTYPENAME")
        voucher_number = _get_text(v, "VOUCHERNUMBER")
        party = _get_text(v, "PARTYLEDGERNAME")
        narration = _get_text(v, "NARRATION")
        # Extract month field for grouping
        month_str = ""
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y%m%d")
                month_str = dt.strftime("%b %Y")
            except ValueError:
                month_str = ""
        ledger_entries = []
        for entry in v.findall("ALLLEDGERENTRIES.LIST"):
            ledger_entries.append({
                "ledger_name": _get_text(entry, "LEDGERNAME"),
                "amount": parse_amount(_get_text(entry, "AMOUNT")),
            })
        # Skip ghost/empty vouchers that Tally TDL sometimes emits
        if not date_str and not voucher_type and not voucher_number:
            continue
        vouchers.append({
            "date": date_str,
            "month": month_str,
            "voucher_type": voucher_type,
            "voucher_number": voucher_number,
            "party_name": party,
            "narration": narration,
            "ledger_entries": ledger_entries,
        })
    if from_date and to_date:
        vouchers = _filter_vouchers_by_date(vouchers, from_date, to_date)
    return vouchers
