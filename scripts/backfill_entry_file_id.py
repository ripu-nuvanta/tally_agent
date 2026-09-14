#!/usr/bin/env python
"""Backfill ``file_id`` onto existing voucher-review data so the original upload,
the live card and the version trail become joinable to ``uploaded_files.id``.

Targets three stores that pre-date the file_id linkage:

  1. ``messages`` voucher_review entries (``data->'entries'[*]``) lacking file_id.
  2. ``voucher_entry_revisions`` rows with a NULL file_id.
  3. ``voucher_entries`` audit rows with a NULL file_id.

For each, we resolve the file_id by matching the entry's ORIGINAL invoice
reference to an ``uploaded_files`` row IN THE SAME CONVERSATION whose
``extracted_data->>'invoice_number'`` equals it — and ONLY when the match is
UNAMBIGUOUS (exactly one upload in that conversation matches). Otherwise we leave
it NULL and log the reason. As a stronger key, a single upload in the
conversation is also accepted (1 upload ⇒ unambiguous).

IMPORTANT — match on the ORIGINAL reference, not the edited one. A card edited
from WTK-06181130-1 → WTK-06181130-111 must still link to its original upload.
So for an entry we prefer its v1 (``version_no=1``) revision reference; that
reflects the as-uploaded value. If no v1 revision exists we fall back to the
entry's own reference, then to the single-upload shortcut.

Idempotent: rows already carrying file_id are skipped. Prints linked vs left-null
counts. Use --dry-run (default) to preview; pass --commit to write.

  PYTHONPATH=. python scripts/backfill_entry_file_id.py --dry-run
  DATABASE_URL=... PYTHONPATH=. python scripts/backfill_entry_file_id.py --commit
"""
from __future__ import annotations

import argparse
import asyncio
import os
from collections import defaultdict

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def _resolve_db_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL (or TEST_DATABASE_URL) to run the backfill.")
    return url


def _norm(ref) -> str | None:
    """Normalise an invoice reference for comparison (trim + casefold)."""
    if ref is None:
        return None
    s = str(ref).strip()
    return s.casefold() if s else None


async def _uploads_by_conversation(session: AsyncSession):
    """Map conversation_id → list of (file_id, normalized_invoice_number)."""
    from backend.db.models import UploadedFile

    rows = (await session.execute(select(UploadedFile))).scalars().all()
    by_conv: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    for uf in rows:
        inv = None
        if isinstance(uf.extracted_data, dict):
            inv = _norm(uf.extracted_data.get("invoice_number"))
        by_conv[str(uf.conversation_id)].append((str(uf.id), inv))
    return by_conv


async def _v1_reference_by_entry(session: AsyncSession):
    """Map (conversation_id, entry_id) → normalized ORIGINAL (v1) reference.

    The v1 revision is the as-uploaded snapshot, so its reference survives later
    edits to the card. Used so edited cards still link to their original upload.
    """
    from backend.db.models import VoucherEntryRevision

    rows = (
        await session.execute(
            select(VoucherEntryRevision).where(VoucherEntryRevision.version_no == 1)
        )
    ).scalars().all()
    out: dict[tuple[str, str], str | None] = {}
    for r in rows:
        data = r.voucher_data if isinstance(r.voucher_data, dict) else {}
        ref = data.get("reference") or data.get("bill_reference")
        out[(str(r.conversation_id), str(r.entry_id))] = _norm(ref)
    return out


def _original_ref(conv_id, entry_id, fallback_ref, v1_refs):
    """Original reference for an entry: prefer v1 revision, else fallback."""
    key = (str(conv_id), str(entry_id)) if entry_id is not None else None
    if key is not None and key in v1_refs and v1_refs[key] is not None:
        return v1_refs[key]
    return _norm(fallback_ref)


def _match_upload(conv_id, ref, by_conv) -> tuple[str | None, str]:
    """Return (file_id, reason). file_id is None when ambiguous/no-match."""
    uploads = by_conv.get(str(conv_id), [])
    if not uploads:
        return None, "no uploads in conversation"
    # Exactly one upload in the conversation ⇒ unambiguous regardless of ref.
    if len(uploads) == 1:
        return uploads[0][0], "single upload in conversation"
    ref_n = _norm(ref)
    if ref_n is None:
        return None, "no reference on entry; multiple uploads"
    matches = [fid for fid, inv in uploads if inv is not None and inv == ref_n]
    if len(matches) == 1:
        return matches[0], "unique invoice_number match"
    if not matches:
        return None, "no invoice_number match among multiple uploads"
    return None, f"ambiguous: {len(matches)} uploads match invoice_number"


async def _backfill_revisions(session, by_conv, v1_refs, commit):
    from backend.db.models import VoucherEntryRevision

    rows = (
        await session.execute(
            select(VoucherEntryRevision).where(VoucherEntryRevision.file_id.is_(None))
        )
    ).scalars().all()
    linked = left = 0
    for r in rows:
        data = r.voucher_data if isinstance(r.voucher_data, dict) else {}
        # Prefer a file_id already inside the snapshot, else match by ORIGINAL
        # (v1) reference so an edited card still links to its original upload.
        fid = data.get("file_id") or None
        if fid is None:
            ref = data.get("reference") or data.get("bill_reference")
            orig = _original_ref(r.conversation_id, r.entry_id, ref, v1_refs)
            fid, reason = _match_upload(r.conversation_id, orig, by_conv)
        else:
            reason = "file_id present in snapshot"
        if fid is None:
            left += 1
            print(f"  revision {r.id} v{r.version_no}: LEFT NULL ({reason})")
            continue
        linked += 1
        print(f"  revision {r.id} v{r.version_no}: -> {fid} ({reason})")
        if commit:
            await session.execute(
                update(VoucherEntryRevision)
                .where(VoucherEntryRevision.id == r.id)
                .values(file_id=fid)
            )
    return linked, left


async def _backfill_messages(session, by_conv, v1_refs, commit):
    from backend.db.models import Message

    rows = (await session.execute(select(Message))).scalars().all()
    linked = left = 0
    for m in rows:
        data = m.data if isinstance(m.data, dict) else None
        if not data or data.get("type") != "voucher_review":
            continue
        entries = data.get("entries")
        if not isinstance(entries, list):
            continue
        changed = False
        for e in entries:
            if not isinstance(e, dict) or e.get("file_id"):
                continue
            ref = e.get("reference") or e.get("bill_reference")
            orig = _original_ref(m.conversation_id, e.get("id"), ref, v1_refs)
            fid, reason = _match_upload(m.conversation_id, orig, by_conv)
            if fid is None:
                left += 1
                print(f"  message {m.id} entry {e.get('id')}: LEFT NULL ({reason})")
                continue
            linked += 1
            e["file_id"] = fid
            changed = True
            print(f"  message {m.id} entry {e.get('id')}: -> {fid} ({reason})")
        if changed and commit:
            # Reassign so SQLAlchemy detects the JSONB mutation.
            from sqlalchemy.orm.attributes import flag_modified

            m.data = dict(data)
            flag_modified(m, "data")
    return linked, left


async def _revision_file_id_by_entry(session: AsyncSession):
    """Map (conversation_id, entry_id) → a non-null file_id from any revision.

    Lets voucher_entries inherit a file_id already resolved on the version trail.
    """
    from backend.db.models import VoucherEntryRevision

    rows = (
        await session.execute(
            select(VoucherEntryRevision).where(VoucherEntryRevision.file_id.isnot(None))
        )
    ).scalars().all()
    out: dict[tuple[str, str], str] = {}
    for r in rows:
        out.setdefault((str(r.conversation_id), str(r.entry_id)), str(r.file_id))
    return out


async def _backfill_voucher_entries(session, by_conv, v1_refs, rev_fids, commit):
    from backend.db.models import VoucherEntry

    rows = (
        await session.execute(
            select(VoucherEntry).where(VoucherEntry.file_id.is_(None))
        )
    ).scalars().all()
    linked = left = 0
    for ve in rows:
        data = ve.voucher_data if isinstance(ve.voucher_data, dict) else {}
        entry_id = data.get("id")
        # (a) Inherit a file_id already resolved on the version trail.
        fid = None
        reason = ""
        if entry_id is not None:
            fid = rev_fids.get((str(ve.conversation_id), str(entry_id)))
            if fid is not None:
                reason = "from revision file_id"
        # (b) Else match by original reference in the same conversation.
        if fid is None:
            ref = data.get("reference") or data.get("bill_reference")
            orig = _original_ref(ve.conversation_id, entry_id, ref, v1_refs)
            fid, reason = _match_upload(ve.conversation_id, orig, by_conv)
        if fid is None:
            left += 1
            print(f"  voucher_entry {ve.id} (entry {entry_id}): LEFT NULL ({reason})")
            continue
        linked += 1
        print(f"  voucher_entry {ve.id} (entry {entry_id}): -> {fid} ({reason})")
        if commit:
            await session.execute(
                update(VoucherEntry)
                .where(VoucherEntry.id == ve.id)
                .values(file_id=fid)
            )
    return linked, left


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", action="store_true", help="Persist changes (default: dry-run).")
    ap.add_argument("--dry-run", action="store_true", help="Preview only (default).")
    args = ap.parse_args()
    commit = args.commit and not args.dry_run

    engine = create_async_engine(_resolve_db_url())
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            by_conv = await _uploads_by_conversation(session)
            v1_refs = await _v1_reference_by_entry(session)
            print(f"Uploaded files across {len(by_conv)} conversations.")
            print(f"Original (v1) references for {len(v1_refs)} entries.\n")
            print("voucher_entry_revisions:")
            r_linked, r_left = await _backfill_revisions(session, by_conv, v1_refs, commit)
            print("\nmessages (voucher_review entries):")
            m_linked, m_left = await _backfill_messages(session, by_conv, v1_refs, commit)
            # voucher_entries can inherit a file_id resolved on the trail above,
            # so build the rev map AFTER revisions are (optionally) committed in
            # memory — but reads are within the same session, so re-query here.
            rev_fids = await _revision_file_id_by_entry(session)
            print("\nvoucher_entries (audit rows):")
            e_linked, e_left = await _backfill_voucher_entries(
                session, by_conv, v1_refs, rev_fids, commit
            )
            if commit:
                await session.commit()
        print("\n=== Summary ===")
        print(f"messages              : linked={m_linked} left_null={m_left}")
        print(f"voucher_entry_revisions: linked={r_linked} left_null={r_left}")
        print(f"voucher_entries        : linked={e_linked} left_null={e_left}")
        print("MODE:", "COMMITTED" if commit else "DRY RUN (no writes)")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
