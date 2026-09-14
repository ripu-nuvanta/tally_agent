"""voucher_entry_revisions.file_id: hard-link each revision back to its original upload

Adds a nullable file_id (FK → uploaded_files.id) + index so the version trail
joins to the originating uploaded_files row. Nullable because legacy rows and
no-file entries (e.g. no-conversation save_draft) lack it.

Revision ID: 005
Revises: 004
Create Date: 2026-06-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "voucher_entry_revisions",
        sa.Column("file_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_voucher_revisions_file_id",
        "voucher_entry_revisions",
        "uploaded_files",
        ["file_id"],
        ["id"],
    )
    op.create_index(
        "ix_voucher_revisions_file_id",
        "voucher_entry_revisions",
        ["file_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_voucher_revisions_file_id", table_name="voucher_entry_revisions")
    op.drop_constraint("fk_voucher_revisions_file_id", "voucher_entry_revisions", type_="foreignkey")
    op.drop_column("voucher_entry_revisions", "file_id")
