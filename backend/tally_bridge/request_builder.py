"""
Build XML request payloads for TallyPrime HTTP API.
All functions are pure — no I/O, no side effects. Each returns an XML string.
Tally date format: DD-MM-YYYY
"""


def _wrap_envelope(header_id: str, body_desc: str) -> str:
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>{header_id}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
{body_desc}
</DESC>
</BODY>
</ENVELOPE>"""


def _wrap_collection_envelope(collection_name: str, object_type: str, native_methods: list[str]) -> str:
    methods_xml = "\n".join(f"<NATIVEMETHOD>{m}</NATIVEMETHOD>" for m in native_methods)
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Collection</TYPE>
<ID>{collection_name}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
</STATICVARIABLES>
<TDL>
<TDLMESSAGE>
<COLLECTION NAME="{collection_name}" ISMODIFY="No">
<TYPE>{object_type}</TYPE>
{methods_xml}
</COLLECTION>
</TDLMESSAGE>
</TDL>
</DESC>
</BODY>
</ENVELOPE>"""


def _wrap_report_envelope(report_id: str, from_date: str, to_date: str, company: str | None = None, extra_vars: str = "") -> str:
    company_var = f"<SVCurrentCompany>{company}</SVCurrentCompany>" if company else ""
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>{report_id}</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
{company_var}
{extra_vars}
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""


# --- Master Queries ---

def build_list_companies() -> str:
    return _wrap_envelope("List of Companies", "")

def build_list_ledgers() -> str:
    return _wrap_collection_envelope("CustomLedgerList", "Ledger", ["Name", "Parent", "ClosingBalance", "OpeningBalance"])

def build_list_groups() -> str:
    return _wrap_collection_envelope("CustomGroupList", "Group", ["Name", "Parent"])

def build_list_stock_items() -> str:
    return _wrap_collection_envelope("CustomStockItemList", "StockItem", ["Name", "Parent", "BaseUnits", "ClosingBalance", "ClosingRate", "ClosingValue"])


# --- Report Queries ---

def build_trial_balance(from_date: str, to_date: str, company: str | None = None) -> str:
    return _wrap_report_envelope("Trial Balance", from_date, to_date, company)

def build_profit_and_loss(from_date: str, to_date: str, company: str | None = None) -> str:
    return _wrap_report_envelope("Profit and Loss", from_date, to_date, company)

def build_balance_sheet(as_on_date: str, company: str | None = None) -> str:
    return _wrap_report_envelope("Balance Sheet", as_on_date, as_on_date, company)

def build_bills_receivable(as_on_date: str, company: str | None = None) -> str:
    return _wrap_report_envelope("Bills Receivable", as_on_date, as_on_date, company)

def build_bills_payable(as_on_date: str, company: str | None = None) -> str:
    return _wrap_report_envelope("Bills Payable", as_on_date, as_on_date, company)

def build_stock_summary(as_on_date: str, stock_group: str | None = None, company: str | None = None) -> str:
    extra = f"<SVSTOCKGROUP>{stock_group}</SVSTOCKGROUP>" if stock_group else ""
    return _wrap_report_envelope("Stock Summary", as_on_date, as_on_date, company, extra)


# --- Voucher Queries ---

def build_day_book(from_date: str, to_date: str, voucher_type: str | None = None, company: str | None = None) -> str:
    extra = f"<VOUCHERTYPENAME>{voucher_type}</VOUCHERTYPENAME>" if voucher_type else ""
    return _wrap_report_envelope("Day Book", from_date, to_date, company, extra)

def build_ledger_vouchers(ledger_name: str, from_date: str, to_date: str, company: str | None = None) -> str:
    return f"""<ENVELOPE>
<HEADER>
<VERSION>1</VERSION>
<TALLYREQUEST>Export</TALLYREQUEST>
<TYPE>Data</TYPE>
<ID>Ledger Vouchers</ID>
</HEADER>
<BODY>
<DESC>
<STATICVARIABLES>
<SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
<SVFROMDATE>{from_date}</SVFROMDATE>
<SVTODATE>{to_date}</SVTODATE>
<LEDGERNAME>{ledger_name}</LEDGERNAME>
{f"<SVCurrentCompany>{company}</SVCurrentCompany>" if company else ""}
</STATICVARIABLES>
</DESC>
</BODY>
</ENVELOPE>"""

def build_sales_register(from_date: str, to_date: str, company: str | None = None) -> str:
    return _wrap_report_envelope("Sales Register", from_date, to_date, company, "<VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>")

def build_purchase_register(from_date: str, to_date: str, company: str | None = None) -> str:
    return _wrap_report_envelope("Purchase Register", from_date, to_date, company, "<VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>")
