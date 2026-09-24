import json
import xml.etree.ElementTree as ET

from v2.probes import p21_full_history_reach as p21
from v2.probes.reads import parse_vouchers

HINDI_BLOCK = ('<VOUCHER VCHTYPE="Sales"><DATE>20230601</DATE><GUID>g-0001</GUID>'
               "<NARRATION>[S0-B:281] Sale to शर्मा ट्रेडर्स&#4;</NARRATION>"
               "<ALLLEDGERENTRIES.LIST><LEDGERNAME>शर्मा ट्रेडर्स</LEDGERNAME><AMOUNT>-11.80</AMOUNT>"
               "<BILLALLOCATIONS.LIST><NAME>Inv/281</NAME><BILLTYPE>New Ref</BILLTYPE><AMOUNT>-11.80</AMOUNT>"
               "</BILLALLOCATIONS.LIST></ALLLEDGERENTRIES.LIST>"
               "<ALLLEDGERENTRIES.LIST><LEDGERNAME>Domestic Sales</LEDGERNAME><AMOUNT>10.00</AMOUNT>"
               "<BILLALLOCATIONS.LIST>  </BILLALLOCATIONS.LIST></ALLLEDGERENTRIES.LIST>"
               "<ALLINVENTORYENTRIES.LIST><STOCKITEMNAME>USB Cable</STOCKITEMNAME><ACTUALQTY> 1 Nos</ACTUALQTY>"
               "<RATE>10.00/Nos</RATE><AMOUNT>10.00</AMOUNT></ALLINVENTORYENTRIES.LIST>"
               "<REFERENCE></REFERENCE></VOUCHER>")


def _response(*blocks: str) -> str:
    return ("<ENVELOPE><BODY><DESC><CMPINFO><VOUCHER>0</VOUCHER></CMPINFO></DESC><DATA><COLLECTION>"
            + "".join(blocks) + "</COLLECTION></DATA></BODY></ENVELOPE>")


def test_voucher_blocks_skip_the_cmpinfo_counter_and_count_utf8_bytes():
    blocks = p21.voucher_blocks(_response(HINDI_BLOCK, HINDI_BLOCK.replace("281", "282")))
    assert len(blocks) == 2 and blocks[0] == HINDI_BLOCK
    assert p21.xml_bytes(HINDI_BLOCK) == len(HINDI_BLOCK.encode("utf-8")) > len(HINDI_BLOCK)


def test_element_json_drops_placeholders_keeps_lists_and_survives_control_chars():
    from v2.agent.tally.xml_utils import sanitize_xml
    doc = p21.element_json(ET.fromstring(sanitize_xml(HINDI_BLOCK)))
    assert doc["@"] == {"VCHTYPE": "Sales"}
    assert doc["NARRATION"] == "[S0-B:281] Sale to शर्मा ट्रेडर्स"
    assert "REFERENCE" not in doc                                                  # empty scalar dropped
    assert len(doc["ALLLEDGERENTRIES.LIST"]) == 2
    assert "BILLALLOCATIONS.LIST" not in doc["ALLLEDGERENTRIES.LIST"][1]           # empty placeholder dropped
    assert doc["ALLLEDGERENTRIES.LIST"][0]["BILLALLOCATIONS.LIST"][0]["NAME"] == "Inv/281"


def test_raw_json_bytes_is_the_compact_utf8_json():
    from v2.agent.tally.xml_utils import sanitize_xml
    expected = json.dumps(p21.element_json(ET.fromstring(sanitize_xml(HINDI_BLOCK))), ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8")
    assert p21.raw_json_bytes(HINDI_BLOCK) == len(expected)


def test_column_bytes_counts_rows_and_sizes_referenced_guids_like_the_vouchers_own():
    short = parse_vouchers(HINDI_BLOCK)[0]
    longer = parse_vouchers(HINDI_BLOCK.replace("<GUID>g-0001</GUID>", "<GUID>g-0001-0123456789</GUID>"))[0]
    (short_bytes, rows), (long_bytes, _) = p21.column_bytes(short), p21.column_bytes(longer)
    assert rows == 5                                  # voucher + 2 ledger lines + 1 inventory line + 1 bill
    assert short_bytes > rows * p21.PG_ROW_OVERHEAD_BYTES
    # Growing the voucher's own GUID by 11 chars grows every GUID-sized reference by 11 bytes too (P5 ruling: each
    # child row also carries a voucher_id column, sized like the voucher's own GUID — Part 1 spec §5 L493-495).
    # Header row: the voucher's own GUID + voucher_type_guid + party_ledger_guid = 3 occurrences.
    # 2 ledger-line rows: each carries ledger_guid + voucher_id = 2 occurrences per row = 4.
    # 1 inventory row: stock_item_guid + voucher_id = 2 occurrences.
    # 1 bill row: (bill) ledger_guid + voucher_id = 2 occurrences.
    # Total = 3 + 4 + 2 + 2 = 11 occurrences, each growing by 11 bytes.
    assert long_bytes - short_bytes == 11 * 11


def test_measure_groups_by_kind_rounds_half_up_and_ignores_unlabelled_tags():
    blocks = {281: HINDI_BLOCK, 282: HINDI_BLOCK.replace("281", "282"), 999: HINDI_BLOCK}
    stats = p21.measure(blocks, {281: "sales+inventory+bills", 282: "sales+inventory+bills"})
    s = stats["sales+inventory+bills"]
    assert list(stats) == ["sales+inventory+bills"] and s["count"] == 2
    assert s["xml_bytes"] == 2 * p21.xml_bytes(HINDI_BLOCK)          # 281 and 282 have the same length
    assert s["xml_per_voucher"] == p21.xml_bytes(HINDI_BLOCK)
    assert s["rows_per_voucher"] == "5.00"


def test_storage_table_from_hand_numbers():
    stats = {"k": {"count": 2, "xml_bytes": 2000, "json_bytes": 1200, "column_bytes": 800, "rows": 10}}
    out = p21.storage_table(stats)
    assert out["per_voucher_bytes"] == {"xml": "1000.0", "raw": "600.0", "columns": "400.0"}
    rows = {(r["vouchers_per_year"], r["years"]): r for r in out["table"]}
    assert len(rows) == 9
    assert rows[(10_000, 2)] == {"vouchers_per_year": 10_000, "years": 2, "vouchers": 20_000, "with_raw_mb": "20.0",
                                 "without_raw_mb": "8.0", "raw_recent_2_fy_only_mb": "20.0"}
    assert rows[(10_000, 5)]["raw_recent_2_fy_only_mb"] == "32.0"          # 50k×400 + 20k×600
    assert rows[(200_000, 10)]["with_raw_mb"] == "2000.0"
    assert out["q22"]["raw_share_pct"] == "60.0"
    assert out["q22"]["per_fy_mb"]["50000"] == {"with_raw": "50.0", "without_raw": "20.0"}
    assert out["q22"]["saving_if_raw_dropped_beyond_2_fy_mb"]["10000"] == {"5": "18.0", "10": "48.0"}


def test_month_chunks_flag_volumes_over_the_chunk_cap():
    stats = {"k": {"count": 1, "xml_bytes": 1000, "json_bytes": 600, "column_bytes": 400, "rows": 5}}
    chunks = {c["vouchers_per_year"]: c for c in p21.storage_table(stats)["q23"]["month_chunks"]}
    assert chunks[10_000] == {"vouchers_per_year": 10_000, "vouchers_per_month": 834, "month_xml_mb": "0.8",
                              "over_chunk_cap": False}
    assert chunks[50_000]["vouchers_per_month"] == 4167 and not chunks[50_000]["over_chunk_cap"]
    assert chunks[200_000]["vouchers_per_month"] == 16667 and chunks[200_000]["over_chunk_cap"]


def test_mean_block_bytes_ignores_empty_placeholders():
    blocks = [HINDI_BLOCK]
    bill = ("<BILLALLOCATIONS.LIST><NAME>Inv/281</NAME><BILLTYPE>New Ref</BILLTYPE><AMOUNT>-11.80</AMOUNT>"
            "</BILLALLOCATIONS.LIST>")
    assert p21.mean_block_bytes(blocks, "BILLALLOCATIONS.LIST") == len(bill.encode("utf-8"))
    assert p21.mean_block_bytes([], "BILLALLOCATIONS.LIST") == 0

