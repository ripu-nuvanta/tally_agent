"""Integration tests — invoice Phase 2 (inventory line items) end-to-end.

Drives Orchestrator.process_file_upload + voucher_action against a real Postgres
session with Vision + stock-item read + the TallyWriter mocked. Gated on
TEST_DATABASE_URL.

Covers:
- a goods purchase (qty-bearing lines, one matched + one new) → entry is
  is_inventory with resolved line_items + available_stock_items.
- voucher_action on that entry → create_stock_item called for the NEW line,
  then the STOCK-based create_purchase_voucher with item tuples + reference.
- a services invoice (no qty) → accounting-only regression (ledger writer).
- sales mirror.
"""
import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.context import SessionContext
from backend.agents.orchestrator import Orchestrator
from backend.api.chat import voucher_action
from backend.api.models import VoucherActionRequest
from backend.db.models import Conversation, User, Workspace
from backend.tally_bridge.client import TallyClient
from backend.tally_bridge.models import StockItem
from tests.fixtures import vision_docs

pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set",
)

_LEDGERS = [
    {"name": "Croma Electronics", "parent_group": "Sundry Creditors"},
    {"name": "Infosys Ltd", "parent_group": "Sundry Debtors"},
    {"name": "Purchase Accounts", "parent_group": "Purchase Accounts"},
    {"name": "Sales Accounts", "parent_group": "Sales Accounts"},
    {"name": "Cash", "parent_group": "Cash-in-hand"},
    {"name": "CGST Input", "parent_group": "Duties & Taxes"},
    {"name": "SGST Input", "parent_group": "Duties & Taxes"},
    {"name": "CGST Output", "parent_group": "Duties & Taxes"},
    {"name": "SGST Output", "parent_group": "Duties & Taxes"},
]
_STOCK_ITEMS = [
    StockItem(name="A4 Paper Ream 500 sheets", parent_group="Primary", base_units="Nos"),
    StockItem(name="HP Laptop 15s", parent_group="Primary", base_units="Nos"),
    StockItem(name="Logitech Wireless Mouse", parent_group="Primary", base_units="Nos"),
]
_SUCCESS = {"success": True, "last_vch_id": "777", "created": 1}


@pytest.fixture(autouse=True)
def _enable_write(monkeypatch):
    from backend.config import settings
    monkeypatch.setattr(settings, "TALLY_WRITE_ENABLED", True)
    monkeypatch.setattr(settings, "TALLY_MODE", "mock")
    monkeypatch.setattr(
        settings, "DATABASE_URL", os.environ["TEST_DATABASE_URL"], raising=False,
    )


@pytest_asyncio.fixture
async def ctx(db_session: AsyncSession):
    user = User(email="invflow@example.com", password_hash="h", name="INV")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    ws = Workspace(user_id=user.id, name="INV Co", config={"mock_mode": True})
    db_session.add(ws)
    await db_session.commit()
    await db_session.refresh(ws)
    conv = Conversation(user_id=user.id, workspace_id=ws.id, title="t")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)
    return user, ws, conv


class _FakeClient:
    async def post_xml(self, xml):
        return "<LEDGERS/>"


async def _upload(db_session, ctx, fixture, content=b"\xff\xd8\xff\xe0PDF"):
    user, ws, conv = ctx
    fd, path = tempfile.mkstemp(suffix=".jpg")
    os.write(fd, content)
    os.close(fd)
    orch = Orchestrator()
    session = SessionContext(session_id=str(conv.id))
    with patch(
        "backend.agents.orchestrator.anthropic_client.messages.create",
        new=AsyncMock(return_value=vision_docs.vision_message(fixture)),
    ), patch(
        "backend.tally_bridge.response_parser.parse_ledger_list",
        return_value=_LEDGERS,
    ), patch(
        "backend.services.stock_resolver.list_stock_items",
        new=AsyncMock(return_value=_STOCK_ITEMS),
    ), patch(
        "backend.tally_bridge.queries.vouchers.get_party_vouchers",
        new=AsyncMock(return_value=[]),
    ), patch(
        "backend.services.dedup.get_party_vouchers",
        new=AsyncMock(return_value=[]),
    ):
        result = await orch.process_file_upload(
            file_path=path, filename="doc.jpg", mime_type="image/jpeg",
            user_message="entry", client=_FakeClient(), session=session,
            file_id="ignored", db=db_session, user_id=str(user.id),
            workspace_id=str(ws.id), conversation_id=str(conv.id),
        )
    os.remove(path)
    return result


@pytest.mark.asyncio
async def test_goods_purchase_entry_is_inventory(db_session, ctx):
    result = await _upload(db_session, ctx, "purchase_goods_inr",
                           content=b"GOODS-PURCHASE-1")
    entry = result["data"]["entries"][0]
    assert entry["is_inventory"] is True
    assert len(entry["line_items"]) == 2
    by_desc = {li["description"]: li for li in entry["line_items"]}
    assert by_desc["A4 Paper Ream 500 sheets"]["matched_item"] == "A4 Paper Ream 500 sheets"
    assert by_desc["Brother Toner Cartridge TN-2380"]["create_new"] is True
    assert "A4 Paper Ream 500 sheets" in entry["available_stock_items"]


@pytest.mark.asyncio
async def test_goods_purchase_writes_stock_voucher(db_session, ctx):
    user, ws, conv = ctx
    result = await _upload(db_session, ctx, "purchase_goods_inr",
                           content=b"GOODS-PURCHASE-2")
    entry = result["data"]["entries"][0]
    entry["conversation_id"] = str(conv.id)
    entry["file_id"] = result["data"]["file_id"]
    req = VoucherActionRequest(action="approve", entry=entry,
                               workspace_id=str(ws.id), session_id=str(conv.id))
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_unit",
        new=AsyncMock(return_value=_SUCCESS),
    ), patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_group",
        new=AsyncMock(return_value=_SUCCESS),
    ), patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_item",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_item, patch(
        "backend.tally_bridge.writer.TallyWriter.create_purchase_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_vch, patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        resp = await voucher_action(
            req, client=TallyClient("localhost", 9000),
            user_id=str(user.id), db=db_session,
        )
    assert resp.data["type"] == "voucher_written"
    m_item.assert_awaited_once()  # only the new line
    m_vch.assert_awaited_once()
    kw = m_vch.await_args.kwargs
    assert len(kw["items"]) == 2
    assert kw["reference"] == "CRO-2026-9001"
    assert kw["reference_date"] == "20260210"
    assert kw["gst_mode"] == "intra"


@pytest.mark.asyncio
async def test_services_purchase_is_accounting_only(db_session, ctx):
    """Regression: a no-qty purchase stays accounting-only (ledger writer)."""
    user, ws, conv = ctx
    result = await _upload(db_session, ctx, "purchase_saas_usd",
                           content=b"SERVICES-PURCHASE-1")
    entry = result["data"]["entries"][0]
    assert entry.get("is_inventory") in (False, None)


@pytest.mark.asyncio
async def test_goods_sales_writes_stock_voucher(db_session, ctx):
    user, ws, conv = ctx
    result = await _upload(db_session, ctx, "sales_goods_inr",
                           content=b"GOODS-SALES-1")
    entry = result["data"]["entries"][0]
    assert entry["is_inventory"] is True
    entry["conversation_id"] = str(conv.id)
    entry["file_id"] = result["data"]["file_id"]
    req = VoucherActionRequest(action="approve", entry=entry,
                               workspace_id=str(ws.id), session_id=str(conv.id))
    with patch(
        "backend.tally_bridge.writer.TallyWriter.create_unit",
        new=AsyncMock(return_value=_SUCCESS),
    ), patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_group",
        new=AsyncMock(return_value=_SUCCESS),
    ), patch(
        "backend.tally_bridge.writer.TallyWriter.create_stock_item",
        new=AsyncMock(return_value=_SUCCESS),
    ), patch(
        "backend.tally_bridge.writer.TallyWriter.create_sales_voucher",
        new=AsyncMock(return_value=_SUCCESS),
    ) as m_vch, patch(
        "backend.services.dedup.get_party_vouchers", new=AsyncMock(return_value=[]),
    ):
        resp = await voucher_action(
            req, client=TallyClient("localhost", 9000),
            user_id=str(user.id), db=db_session,
        )
    assert resp.data["type"] == "voucher_written"
    m_vch.assert_awaited_once()
    assert m_vch.await_args.kwargs["party"] == "Infosys Ltd"
    assert m_vch.await_args.kwargs["items"][0][3] == "Sales Accounts"
