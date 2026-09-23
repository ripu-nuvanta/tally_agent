"""Is company A still the seed company's known state? (S0 spec §4.2)

Bills totals come from docs/seed-data-setup.md. The TB rows are compared with the baseline probe 0 captured
right after the restore (tests/fixtures/trial_balance_live.xml is another company and is never used here).
`check_anchors` captures fixtures (probe 0); `check_anchors_direct` doesn't (the anchors steps in ordered runs, §6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from v2.agent.tally.client import TallyClient
from v2.agent.tally.envelopes import build_company_list, wrap_report
from v2.agent.tally.reports import parse_bills, parse_trial_balance
from v2.agent.tally.xml_utils import parse_company_list, sanitize_xml
from v2.probes.context import ProbeContext
from v2.probes.safety import check_company, check_request

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


def _requests(company: str) -> tuple[str, str, str]:
    return (wrap_report("Bills Receivable", ANCHOR_DATE, ANCHOR_DATE, company),
            wrap_report("Bills Payable", ANCHOR_DATE, ANCHOR_DATE, company),
            wrap_report("Trial Balance", ANCHOR_FROM, ANCHOR_DATE, company))


def _evaluate(receivable_text: str, payable_text: str, tb_text: str,
              tb_baseline: dict[str, str] | None) -> AnchorResult:
    receivable = _bills_total(receivable_text)
    payable = _bills_total(payable_text)
    tb_rows = {row["account_name"]: str(row["closing_balance"]) for row in parse_trial_balance(tb_text)}
    result = AnchorResult(receivable=receivable, payable=payable, tb_rows=tb_rows)
    if receivable != SEED_RECEIVABLE:
        result.problems.append(f"Bills Receivable {receivable} ≠ {SEED_RECEIVABLE}")
    if payable != SEED_PAYABLE:
        result.problems.append(f"Bills Payable {payable} ≠ {SEED_PAYABLE}")
    if tb_baseline is not None and tb_rows != tb_baseline:
        result.problems.append("TB group rows differ from probe 0's baseline")
    return result


async def check_anchors(ctx: ProbeContext, step_prefix: str, tb_baseline: dict[str, str] | None) -> AnchorResult:
    receivable_xml, payable_xml, tb_xml = _requests(ctx.company_name)
    receivable_text = await ctx.send(f"{step_prefix}_bills_receivable", receivable_xml)
    payable_text = await ctx.send(f"{step_prefix}_bills_payable", payable_xml)
    tb_text = await ctx.send(f"{step_prefix}_tb", tb_xml)
    return _evaluate(receivable_text, payable_text, tb_text, tb_baseline)


async def _post(client: TallyClient, xml: str) -> str:
    check_request(xml)
    return sanitize_xml((await client.post_xml(xml)).text)


async def check_anchors_direct(client: TallyClient, company: str, tb_baseline: dict[str, str]) -> AnchorResult:
    """The same check, uncaptured, after the company guard (S0 spec §4.2, §6 anchors steps).

    Raises GuardError, TallyConnectionError or TallyResponseError; the runner records them as a failed check.
    """
    check_company(parse_company_list(await _post(client, build_company_list())), company, mutating=False)
    receivable_xml, payable_xml, tb_xml = _requests(company)
    receivable_text = await _post(client, receivable_xml)
    payable_text = await _post(client, payable_xml)
    tb_text = await _post(client, tb_xml)
    return _evaluate(receivable_text, payable_text, tb_text, tb_baseline)
