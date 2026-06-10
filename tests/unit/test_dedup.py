"""Unit tests — duplicate detection (Phase 1 Part B).

Covers:
- sha256_bytes (pure).
- B1 exact-file match + per-workspace isolation (DB-backed, gated on TEST_DATABASE_URL).
- B2 business-key match against prior written VoucherEntry rows (DB-backed).
- B2 Tally-reference match via get_party_vouchers (mock client).
- no-invoice-no path → B2 skipped.
- Tally query error → does not crash (still applies B1 + DB B2).
"""
import os
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.dedup import (
    find_business_key_duplicate,
    find_duplicate,
    sha256_bytes,
)

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)


# --- sha256 (pure, no DB) ---

def test_sha256_bytes_is_deterministic_hex():
    h = sha256_bytes(b"hello world")
    assert h == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert sha256_bytes(b"hello world") == h


def test_sha256_bytes_differs_on_content():
    assert sha256_bytes(b"a") != sha256_bytes(b"b")


# --- DB fixtures ---

@pytest_asyncio.fixture
async def seeded(db_session: AsyncSession):
    from backend.db.models import (
        Conversation,
        UploadedFile,
        User,
        VoucherEntry,
        Workspace,
    )
    user = User(email="dedup@example.com", password_hash="h", name="D")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    ws = Workspace(user_id=user.id, name="WS-A")
    ws2 = Workspace(user_id=user.id, name="WS-B")
    db_session.add_all([ws, ws2])
    await db_session.commit()
    await db_session.refresh(ws)
    await db_session.refresh(ws2)
    conv = Conversation(user_id=user.id, workspace_id=ws.id, title="t")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Prior uploaded file with a known hash in WS-A.
    prior_file = UploadedFile(
        user_id=user.id, workspace_id=ws.id, conversation_id=conv.id,
        filename="orig.pdf", mime_type="application/pdf", file_size=10,
        storage_path="/tmp/orig.pdf", status="written",
        content_hash="HASH_A",
    )
    db_session.add(prior_file)
    await db_session.commit()
    await db_session.refresh(prior_file)

    # Prior written voucher for party "Acme" with reference "INV-100".
    ve = VoucherEntry(
        file_id=prior_file.id, user_id=user.id, workspace_id=ws.id,
        conversation_id=conv.id, voucher_type="Purchase",
        voucher_data={"party_ledger": "Acme", "reference": "INV-100"},
        status="written", tally_voucher_number="P-7",
    )
    db_session.add(ve)
    await db_session.commit()

    return {"user": user, "ws": ws, "ws2": ws2, "conv": conv, "prior_file": prior_file}


class _FakeClient:
    """TallyClient stand-in; get_party_vouchers is patched separately."""


# --- B1 exact-file ---

@pytest.mark.asyncio
async def test_b1_same_hash_same_workspace_is_duplicate(db_session, seeded):
    with patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="HASH_A",
            party_ledger="Unrelated", invoice_ref=None, company="Co",
        )
    assert dup is not None
    assert dup["reason"] == "same file"


@pytest.mark.asyncio
async def test_b1_same_hash_different_workspace_is_not_duplicate(db_session, seeded):
    with patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws2"].id), content_hash="HASH_A",
            party_ledger="Unrelated", invoice_ref=None, company="Co",
        )
    assert dup is None


# --- B2 business key: VoucherEntry ---

@pytest.mark.asyncio
async def test_b2_voucherentry_match_is_duplicate(db_session, seeded):
    with patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="DIFFERENT",
            party_ledger="Acme", invoice_ref="INV-100", company="Co",
        )
    assert dup is not None
    assert dup["reason"] == "same invoice no for party"
    assert dup["voucher_no"] == "P-7"


@pytest.mark.asyncio
async def test_b2_voucherentry_different_party_not_duplicate(db_session, seeded):
    with patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="DIFFERENT",
            party_ledger="OtherParty", invoice_ref="INV-100", company="Co",
        )
    assert dup is None


# --- B2 business key: Tally ---

@pytest.mark.asyncio
async def test_b2_tally_reference_match_is_duplicate(db_session, seeded):
    tally_rows = [
        {"voucher_number": "T-55", "date": "01-05-2026", "reference": "INV-200",
         "voucher_type": "Purchase"},
    ]
    with patch(
        "backend.services.dedup.get_party_vouchers",
        new=AsyncMock(return_value=tally_rows),
    ):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="DIFFERENT",
            party_ledger="SomeSupplier", invoice_ref="INV-200", company="Co",
        )
    assert dup is not None
    assert dup["reason"] == "same invoice no for party"
    assert dup["voucher_no"] == "T-55"
    assert dup["date"] == "01-05-2026"


# --- Edge: no invoice ref → B2 skipped ---

@pytest.mark.asyncio
async def test_no_invoice_ref_skips_b2(db_session, seeded):
    mock = AsyncMock(return_value=[])
    with patch("backend.services.dedup.get_party_vouchers", new=mock):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="DIFFERENT",
            party_ledger="Acme", invoice_ref=None, company="Co",
        )
    assert dup is None
    mock.assert_not_awaited()  # Tally not queried when no invoice ref


# --- Defensive: Tally query error doesn't crash ---

@pytest.mark.asyncio
async def test_tally_query_error_does_not_crash(db_session, seeded):
    with patch(
        "backend.services.dedup.get_party_vouchers",
        new=AsyncMock(side_effect=RuntimeError("tally down")),
    ):
        # No DB match either → should return None, not raise.
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="DIFFERENT",
            party_ledger="SomeSupplier", invoice_ref="INV-999", company="Co",
        )
    assert dup is None


@pytest.mark.asyncio
async def test_tally_error_still_applies_db_b2(db_session, seeded):
    """Even if Tally is down, a DB VoucherEntry match still blocks."""
    with patch(
        "backend.services.dedup.get_party_vouchers",
        new=AsyncMock(side_effect=RuntimeError("tally down")),
    ):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="DIFFERENT",
            party_ledger="Acme", invoice_ref="INV-100", company="Co",
        )
    assert dup is not None
    assert dup["voucher_no"] == "P-7"


# --- Finding 2: normalize keys (strip + casefold) on both B2 sides ---

@pytest.mark.asyncio
async def test_b2_db_match_ignores_whitespace_and_case(db_session, seeded):
    """DB B2: 'inv-100 ' vs stored 'INV-100' (and ' acme ' vs 'Acme') still matches."""
    with patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="DIFFERENT",
            party_ledger="  acme  ", invoice_ref="inv-100 ", company="Co",
        )
    assert dup is not None
    assert dup["voucher_no"] == "P-7"


@pytest.mark.asyncio
async def test_b2_tally_match_ignores_whitespace_and_case(db_session, seeded):
    """Tally B2: a stored REFERENCE 'INV-200\\n' matches incoming 'inv-200'."""
    tally_rows = [
        {"voucher_number": "T-55", "date": "01-05-2026", "reference": "INV-200\n",
         "voucher_type": "Purchase"},
    ]
    with patch(
        "backend.services.dedup.get_party_vouchers",
        new=AsyncMock(return_value=tally_rows),
    ):
        dup = await find_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id), content_hash="DIFFERENT",
            party_ledger="SomeSupplier", invoice_ref="inv-200", company="Co",
        )
    assert dup is not None
    assert dup["voucher_no"] == "T-55"


# --- Finding 1 helper: find_business_key_duplicate (B2 only, no file hash) ---

@pytest.mark.asyncio
async def test_business_key_helper_matches_db_voucherentry(db_session, seeded):
    with patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        dup = await find_business_key_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id),
            party_ledger="Acme", invoice_ref="INV-100", company="Co",
        )
    assert dup is not None
    assert dup["voucher_no"] == "P-7"
    assert dup["reason"] == "same invoice no for party"


@pytest.mark.asyncio
async def test_business_key_helper_no_ref_returns_none(db_session, seeded):
    """Empty reference → no business-key block (consistent with upload-time B2-skip)."""
    mock = AsyncMock(return_value=[])
    with patch("backend.services.dedup.get_party_vouchers", new=mock):
        dup = await find_business_key_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id),
            party_ledger="Acme", invoice_ref="", company="Co",
        )
    assert dup is None
    mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_business_key_helper_distinct_ref_returns_none(db_session, seeded):
    """A corrected/edited reference that is no longer a dup → allowed (None)."""
    with patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        dup = await find_business_key_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id),
            party_ledger="Acme", invoice_ref="INV-NEW-999", company="Co",
        )
    assert dup is None


@pytest.mark.asyncio
async def test_business_key_helper_normalizes(db_session, seeded):
    with patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        dup = await find_business_key_duplicate(
            db_session, _FakeClient(),
            workspace_id=str(seeded["ws"].id),
            party_ledger="ACME", invoice_ref="  inv-100", company="Co",
        )
    assert dup is not None
    assert dup["voucher_no"] == "P-7"
