"""Probe 21: full-history reach and size (S0 spec §7 "Probe 21", B part). Feeds decision 7b, Q22, Q23, R27.

Reach: fetch FY 2022-23 (company B's first year, three FYs behind the current one) month by month with probe 5's
confirmed request. Every month's tags must equal the dataset's (company_b_view.compare_tags; the cancelled pair is
reported, not judged, because probe 3's B part owns the flags, S0-D7).
Size: measure bytes per voucher by kind in three forms. Raw XML; a generic JSON of the whole voucher (the stand-in for
S1's `raw` JSONB); and the Part 1 §5 minimum columns plus a per-row overhead (the stand-in for S1's typed rows). Then
extrapolate to 10k/50k/200k vouchers a year × 2/5/10 years, with and without `raw`. Those are the numbers Q22 and Q23
wait on.
Timings are recorded and labelled "Wine — not representative". The tier-C timing half stays ⏭ (Q29).
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any

from v2.agent.tally.xml_utils import sanitize_xml
from v2.probes.reads import parse_vouchers, primary_lines

PG_ROW_OVERHEAD_BYTES = 28      # PostgreSQL heap tuple header (23 B, aligned to 24) + 4-byte line pointer
VOLUMES = (10_000, 50_000, 200_000)
YEARS = (2, 5, 10)
RECENT_FYS_WITH_RAW = 2         # Q22's option: keep `raw` only for the 2-FY window
CHUNK_CAP_VOUCHERS = 5_000      # Part 1 §5 extractor: day/month chunks capped at about 5k vouchers
BLOCK_TAGS = ("ALLLEDGERENTRIES.LIST", "ALLINVENTORYENTRIES.LIST", "BILLALLOCATIONS.LIST")
_MB = Decimal(10) ** 6
_BLOCK = re.compile(r"<VOUCHER\b[^>]*>(.*?)</VOUCHER>", re.S)


def voucher_blocks(raw_text: str) -> list[str]:
    """Each <VOUCHER>…</VOUCHER> exactly as sent. CMPINFO's childless <VOUCHER>0</VOUCHER> counter is skipped."""
    return [m.group(0) for m in _BLOCK.finditer(raw_text) if "<" in m.group(1)]


def xml_bytes(block: str) -> int:
    return len(block.encode("utf-8"))


def element_json(element: ET.Element) -> Any:
    """A generic XML → JSON walk: `.LIST` children become arrays, attributes go under "@", and empty placeholders and
    empty scalars are dropped. This is the stand-in for S1's `raw` JSONB."""
    children = [c for c in element if len(c) or (c.text or "").strip()]
    text = (element.text or "").strip()
    if not children:
        return {"@": dict(element.attrib), "#": text} if element.attrib else text
    out: dict[str, Any] = {"@": dict(element.attrib)} if element.attrib else {}
    for child in children:
        value = element_json(child)
        if child.tag.endswith(".LIST"):
            out.setdefault(child.tag, []).append(value)
        else:
            out[child.tag] = value
    return out


def _compact(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def raw_json_bytes(block: str) -> int:
    return _compact(element_json(ET.fromstring(sanitize_xml(block))))


def column_bytes(voucher: dict) -> tuple[int, int]:
    """(bytes, rows) of the Part 1 §5 minimum columns for one voucher: compact JSON of the values, plus
    PG_ROW_OVERHEAD_BYTES per row. Referenced GUIDs are sized like the voucher's own. Indexes are excluded.

    Part 1 spec §5 (docs/specs/2026-09-21-bi-part1-sync-design.md L493-495): `tally_voucher_ledger_lines`,
    `tally_voucher_inventory_lines` and `tally_bill_allocations` each carry a `voucher_id` column (the child row's
    foreign key back to its voucher). It is sized like the voucher's own exported GUID, same as every other
    referenced GUID column here.
    """
    h = voucher["header"]
    ref = "g" * len(h.get("GUID", ""))
    lines = primary_lines(voucher)
    rows: list[list[str]] = [[h.get("GUID", ""), h.get("MASTERID", ""), h.get("ALTERID", ""), h.get("DATE", ""),
                              ref, h.get("VOUCHERTYPENAME", ""), h.get("VOUCHERNUMBER", ""), h.get("REFERENCE", ""),
                              ref, h.get("NARRATION", ""), h.get("ISCANCELLED", ""), h.get("ISOPTIONAL", ""),
                              h.get("ISPOSTDATED", ""), "No"]]
    rows += [[ref, ref, ln["fields"].get("LEDGERNAME", ""), ln["fields"].get("AMOUNT", ""),
              ln["fields"].get("ISDEEMEDPOSITIVE", "")] for ln in lines]
    rows += [[ref, ref, inv["fields"].get("ACTUALQTY", ""), inv["fields"].get("RATE", ""),
              inv["fields"].get("AMOUNT", "")] for inv in voucher["inventory"]]
    rows += [[ref, ref, bill.get("NAME", ""), bill.get("BILLTYPE", ""), bill.get("AMOUNT", ""),
              bill.get("BILLCREDITPERIOD", "")] for ln in lines for bill in ln["bills"]]
    return sum(_compact(row) for row in rows) + PG_ROW_OVERHEAD_BYTES * len(rows), len(rows)


def _mean(total: int, count: int) -> int:
    return int((Decimal(total) / count).quantize(Decimal("1"), ROUND_HALF_UP)) if count else 0


def measure(blocks: dict[int, str], labels: dict[int, str]) -> dict[str, dict[str, Any]]:
    """Per kind label: totals and per-voucher means. Tags without a label (flagged, untagged, outside the window)
    are left out."""
    stats: dict[str, dict[str, Any]] = {}
    for tag, block in sorted(blocks.items()):
        label = labels.get(tag)
        if label is None:
            continue
        cols, rows = column_bytes(parse_vouchers(block)[0])
        s = stats.setdefault(label, {"count": 0, "xml_bytes": 0, "json_bytes": 0, "column_bytes": 0, "rows": 0})
        s["count"] += 1
        s["xml_bytes"] += xml_bytes(block)
        s["json_bytes"] += raw_json_bytes(block)
        s["column_bytes"] += cols
        s["rows"] += rows
    for s in stats.values():
        s["xml_per_voucher"] = _mean(s["xml_bytes"], s["count"])
        s["json_per_voucher"] = _mean(s["json_bytes"], s["count"])
        s["column_per_voucher"] = _mean(s["column_bytes"], s["count"])
        s["rows_per_voucher"] = str((Decimal(s["rows"]) / s["count"]).quantize(Decimal("0.01"), ROUND_HALF_UP))
    return stats


def mean_block_bytes(blocks: list[str], list_tag: str) -> int:
    """Mean bytes of one non-empty `list_tag` block. It lets S1 scale to invoices with more lines than company B's
    (every company-B invoice carries exactly one stock line)."""
    pattern = re.compile(rf"<{re.escape(list_tag)}>(.*?)</{re.escape(list_tag)}>", re.S)
    found = [m.group(0) for block in blocks for m in pattern.finditer(block) if m.group(1).strip()]
    return _mean(sum(xml_bytes(f) for f in found), len(found))


def _mb(n: Decimal) -> str:
    return str((n / _MB).quantize(Decimal("0.1"), ROUND_HALF_UP))


def storage_table(stats: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Q22/Q23 inputs from the measured mix. Weights = the measured kinds' counts (company B's FY 2022-23)."""
    n = sum(s["count"] for s in stats.values())
    per = {key: Decimal(sum(s[total] for s in stats.values())) / n
           for key, total in (("xml", "xml_bytes"), ("raw", "json_bytes"), ("columns", "column_bytes"))}
    with_raw = per["columns"] + per["raw"]
    table = []
    for volume in VOLUMES:
        for years in YEARS:
            vouchers = Decimal(volume * years)
            recent = Decimal(volume * min(years, RECENT_FYS_WITH_RAW))
            table.append({"vouchers_per_year": volume, "years": years, "vouchers": volume * years,
                          "with_raw_mb": _mb(vouchers * with_raw), "without_raw_mb": _mb(vouchers * per["columns"]),
                          "raw_recent_2_fy_only_mb": _mb(vouchers * per["columns"] + recent * per["raw"])})
    chunks = []
    for volume in VOLUMES:
        per_month = int((Decimal(volume) / 12).quantize(Decimal("1"), ROUND_CEILING))
        chunks.append({"vouchers_per_year": volume, "vouchers_per_month": per_month,
                       "month_xml_mb": _mb(per_month * per["xml"]), "over_chunk_cap": per_month > CHUNK_CAP_VOUCHERS})
    return {
        "per_voucher_bytes": {k: str(v.quantize(Decimal("0.1"), ROUND_HALF_UP)) for k, v in per.items()},
        "mix_vouchers": n,
        "table": table,
        "q22": {"raw_share_pct": str((per["raw"] / with_raw * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)),
                "per_fy_mb": {str(v): {"with_raw": _mb(v * with_raw), "without_raw": _mb(v * per["columns"])}
                              for v in VOLUMES},
                "saving_if_raw_dropped_beyond_2_fy_mb": {
                    str(v): {str(y): _mb(Decimal(v * (y - RECENT_FYS_WITH_RAW)) * per["raw"])
                             for y in YEARS if y > RECENT_FYS_WITH_RAW} for v in VOLUMES}},
        "q23": {"per_extra_fy_with_raw_mb": {str(v): _mb(v * with_raw) for v in VOLUMES},
                "per_extra_fy_without_raw_mb": {str(v): _mb(v * per["columns"]) for v in VOLUMES},
                "month_chunks": chunks,
                "caveats": ["indexes excluded", "JSONB stored size ≈ text JSON (not modelled)",
                            "company B's mix: one stock line per invoice — scale with block_bytes"]},
    }
