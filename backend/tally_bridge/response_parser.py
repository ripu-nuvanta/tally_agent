"""
Parse TallyPrime XML responses into normalized Python dicts.
Handles Tally's inconsistent casing, empty tags, comma-formatted amounts.
"""
import xml.etree.ElementTree as ET


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
        root = ET.fromstring(raw_xml)
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
    root = ET.fromstring(raw_xml)
    rows = []
    for acc in root.iter("DSPACCNAME"):
        name = _get_text(acc, "DSPDISPNAME")
        if not name:
            continue
        rows.append({
            "account_name": name,
            "debit_amount": parse_amount(_get_text(acc, "DSPCLDRAMT")),
            "credit_amount": parse_amount(_get_text(acc, "DSPCLCRAMT")),
            "closing_balance": _get_text(acc, "DSPCLAMT"),
        })
    return rows


def parse_ledger_list(raw_xml: str) -> list[dict]:
    root = ET.fromstring(raw_xml)
    ledgers = []
    for ledger in root.iter("LEDGER"):
        name = _get_text(ledger, "NAME")
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
    return parse_trial_balance(raw_xml)


def parse_balance_sheet(raw_xml: str) -> list[dict]:
    return parse_trial_balance(raw_xml)


def parse_bills(raw_xml: str) -> list[dict]:
    root = ET.fromstring(raw_xml)
    bills = []
    for bill in root.iter("BILLSFIXED"):
        name = _get_text(bill, "BILLNAME")
        if not name:
            continue
        bills.append({
            "bill_number": name,
            "party_name": _get_text(bill, "BILLPARTY"),
            "bill_date": _get_text(bill, "BILLDATE"),
            "amount": abs(parse_amount(_get_text(bill, "BILLAMOUNT"))),
            "pending_amount": abs(parse_amount(_get_text(bill, "BILLPENDING"))),
        })
    return bills


def parse_stock_summary(raw_xml: str) -> list[dict]:
    root = ET.fromstring(raw_xml)
    items = []
    for item in root.iter("STOCKITEM"):
        name = _get_text(item, "NAME")
        if not name:
            continue
        closing_bal = _get_text(item, "CLOSINGBALANCE")
        qty = 0.0
        if closing_bal:
            parts = closing_bal.split()
            if parts:
                try:
                    qty = float(parts[0].replace(",", ""))
                except ValueError:
                    pass
        items.append({
            "name": name,
            "parent_group": _get_text(item, "PARENT"),
            "base_units": _get_text(item, "BASEUNITS"),
            "closing_quantity": qty,
            "closing_rate": parse_amount(_get_text(item, "CLOSINGRATE")),
            "closing_value": parse_amount(_get_text(item, "CLOSINGVALUE")),
        })
    return items


def parse_vouchers(raw_xml: str) -> list[dict]:
    root = ET.fromstring(raw_xml)
    vouchers = []
    for v in root.iter("VOUCHER"):
        date_str = _get_text(v, "DATE")
        voucher_type = _get_text(v, "VOUCHERTYPENAME")
        voucher_number = _get_text(v, "VOUCHERNUMBER")
        party = _get_text(v, "PARTYLEDGERNAME")
        narration = _get_text(v, "NARRATION")
        ledger_entries = []
        for entry in v.findall("ALLLEDGERENTRIES.LIST"):
            ledger_entries.append({
                "ledger_name": _get_text(entry, "LEDGERNAME"),
                "amount": parse_amount(_get_text(entry, "AMOUNT")),
            })
        vouchers.append({
            "date": date_str,
            "voucher_type": voucher_type,
            "voucher_number": voucher_number,
            "party_name": party,
            "narration": narration,
            "ledger_entries": ledger_entries,
        })
    return vouchers
