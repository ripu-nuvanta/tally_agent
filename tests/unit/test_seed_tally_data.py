"""Unit tests for scripts/seed_tally_data.py helpers.

Pure-helper tests only — does not exercise the writer or live Tally.
"""
from scripts.seed_tally_data import _compute_gross
from scripts.seed_data import bharat_traders as bt


def test_compute_gross_single_rate():
    # 2 * 100 = 200 base; 18% GST = 36; gross = 236.0
    items = [("X", 2, 100, "L", "Nos", 18)]
    assert _compute_gross(items, gst_mode="intra") == 236.0


def test_compute_gross_multi_rate():
    # 100@18% (base 100, tax 18) + 200@12% (base 200, tax 24) = 342.0
    items = [
        ("A", 1, 100, "L", "Nos", 18),
        ("B", 2, 100, "L", "Nos", 12),
    ]
    assert _compute_gross(items, gst_mode="intra") == 342.0


def test_compute_gross_zero_rate_no_tax():
    # gst_rate=0 → no tax added
    items = [("Z", 5, 100, "L", "Nos", 0)]
    assert _compute_gross(items, gst_mode="intra") == 500.0


def test_compute_gross_groups_same_rate():
    # Two 18% lines should pool into one tax bucket: base 1000, tax 180 → 1180
    items = [
        ("A", 5, 100, "L", "Nos", 18),
        ("B", 5, 100, "L", "Nos", 18),
    ]
    assert _compute_gross(items, gst_mode="intra") == 1180.0


def test_compute_gross_s001_snapshot():
    """Snapshot: bt.SALES_INVOICES[0] (S001) is HP Laptop 15s 2*45000 + Logitech Mouse 5*800.
    Both 18% → base 94000, tax 16920, gross 110920.00.
    """
    s001 = bt.SALES_INVOICES[0]
    assert s001[0] == "S001"
    lines = s001[3]  # [(item, qty, rate), ...]
    # Mirror what _build_voucher_items would produce — only gst_rate matters here.
    meta = {
        name: gst
        for name, _g, _u, _s, _oq, _or, _ov, _h, gst in bt.STOCK_ITEMS
    }
    items = [(n, q, r, "L", "Nos", meta[n]) for n, q, r in lines]
    assert _compute_gross(items, gst_mode="intra") == 110920.00
